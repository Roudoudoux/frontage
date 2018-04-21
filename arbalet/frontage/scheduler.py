
import json
import datetime
import time

from time import sleep
from utils.red import redis, redis_get
from frontage import Frontage
from tasks.tasks import start_fap, start_default_fap, clear_all_task
from scheduler_state import SchedulerState

from apps.fap import Fap
from apps.flags import Flags
from apps.random_flashing import RandomFlashing
from apps.sweep_async import SweepAsync
from apps.sweep_rand import SweepRand
from apps.snap import Snap
from apps.snake import Snake
from apps.tetris import Tetris
from utils.sentry_client import SENTRY
from server.flaskutils import print_flush
from db.models import ConfigModel
from db.base import session_factory


EXPIRE_SOON_DELAY = 5


class Scheduler(object):

    def __init__(self, port=33460, hardware=True, simulator=True):
        print_flush('---> Waiting for frontage connection...')
        clear_all_task()
        self.frontage = Frontage(port, hardware)

        session = session_factory()
        config = session.query(ConfigModel).first()
        if not config:
            conf = ConfigModel(expires_delay=60)
            session.add(conf)
            session.commit()

        expires = session.query(ConfigModel).all()
        print_flush('--------- DB APP ---')
        for e in expires:
            print_flush(e)
        session.close()
        print_flush('--------------------')

        redis.set(SchedulerState.KEY_USERS_Q, '[]')
        redis.set(SchedulerState.KEY_FORCED_APP, False)

        # SchedulerState.set_current_app({})

        # Dict { Name: ClassName, Start_at: XXX, End_at: XXX, task_id: XXX}
        self.current_app_state = None
        self.queue = None
        # Struct { ClassName : Instance, ClassName: Instance }
        # app.__class__.__name__
        self.apps = {Flags.__name__: Flags(),
                     SweepAsync.__name__: SweepAsync(),
                     Snake.__name__: Snake(),
                     SweepRand.__name__: SweepRand(),
                     Snap.__name__: Snap(),
                     Tetris.__name__: Tetris(),
                     RandomFlashing.__name__: RandomFlashing()}

        SchedulerState.set_registered_apps(self.apps)
        # Set schduled time for app, in minutes
        redis.set(SchedulerState.KEY_SCHEDULED_APP_TIME,
                  SchedulerState.DEFAULT_APP_SCHEDULE_TIME)
    # def start_ne

    def keep_alive_waiting_app(self):
        queue = SchedulerState.get_user_app_queue()
        for c_app in list(queue):
            # Not alive since last check ?
            if time.time() > (
                    c_app['last_alive'] +
                    SchedulerState.DEFAULT_KEEP_ALIVE_DELAY):
                # to_remove.append(i)
                queue.remove(c_app)

        # current_app = SchedulerState.get_current_app()
        # if time.time() > (current_app['last_alive'] + SchedulerState.DEFAULT_KEEP_ALIVE_DELAY):
        #     SchedulerState.stop_app(current_app, Fap.CODE_EXPIRE, 'someone else turn')

    def check_on_off_table(self):
        now = datetime.datetime.now()
        sunrise = SchedulerState.get_scheduled_off_time()
        sunset = SchedulerState.get_scheduled_on_time()


        if sunset > sunrise:
            sunrise = sunrise + datetime.timedelta(days=1)

        if sunset < now and now < sunrise:
            SchedulerState.set_frontage_on(True)
        else:
            SchedulerState.set_frontage_on(False)

    def disable_frontage(self):
        SchedulerState.clear_user_app_queue()
        SchedulerState.stop_app(SchedulerState.get_current_app(),
                                Fap.CODE_CLOSE_APP,
                                'The admin started a forced app')

    def run_scheduler(self):
        # check usable value, based on ON/OFF AND if a forced app is running
        SchedulerState.set_usable((not SchedulerState.get_forced_app() == 'True') and SchedulerState.is_frontage_on())
        enable_state = SchedulerState.get_enable_state()
        if enable_state == 'scheduled':
            self.check_on_off_table()
        elif enable_state == 'on':
            SchedulerState.set_frontage_on(True)
        elif enable_state == 'off':
            SchedulerState.set_frontage_on(False)

        if SchedulerState.is_frontage_on():
            self.check_app_scheduler()
        else:
            # improvement : add check to avoid erase in each loop
            self.disable_frontage()
            self.frontage.erase_all()

    def stop_current_app_start_next(self, queue, c_app, next_app):
        print_flush('===> REVOKING APP, someone else turn')
        SchedulerState.stop_app(c_app, Fap.CODE_EXPIRE, 'someone else turn')
        # Start app
        start_fap.apply_async(args=[next_app], queue='userapp')
        print_flush("## Starting {} [case A]".format(next_app['name']))
        # Remove app form waiting Q
        SchedulerState.pop_user_app_queue(queue)

    def app_is_expired(self, c_app):
        now = datetime.datetime.now()

        return now > datetime.datetime.strptime(c_app['expire_at'], "%Y-%m-%d %H:%M:%S.%f")

    def start_default_app(self):
        default_scheduled_app = SchedulerState.get_next_default_app()
        if default_scheduled_app:
            next_app = {'name': default_scheduled_app.name,
                        'params': default_scheduled_app.default_params,
                        'expires': default_scheduled_app.duration}

            if not next_app['expires'] or next_app['expires'] == 0:
                next_app['expires'] = (15 * 60)
            start_default_fap.apply_async(args=[next_app], queue='userapp')
            SchedulerState.wait_task_to_start()
            print_flush("## Starting {} [DEFAULT]".format(next_app['name']))

    def check_app_scheduler(self):
        # check keep alive app (in user waiting app Q)
        self.keep_alive_waiting_app()

        # collect usefull struct & data
        queue = SchedulerState.get_user_app_queue()  # User waiting app
        c_app = SchedulerState.get_current_app()  # Current running app
        now = datetime.datetime.now()

        # Is a app running ?
        if c_app:
            # is expire soon ?
            if now > (datetime.datetime.strptime(c_app['expire_at'], "%Y-%m-%d %H:%M:%S.%f") - datetime.timedelta(seconds=EXPIRE_SOON_DELAY)):
                if not SchedulerState.get_expire_soon():
                    Fap.send_expires_soon(EXPIRE_SOON_DELAY)
            # is the current_app expired ?
            if self.app_is_expired(c_app) or c_app.get('is_default', False):
                # is the current_app a FORCED_APP ?
                if redis_get(SchedulerState.KEY_FORCED_APP, False) == 'True':
                    SchedulerState.stop_app(c_app)
                    return
                # is some user-app are waiting in queue ?
                if len(queue) > 0:
                    next_app = queue[0]
                    self.stop_current_app_start_next(queue, c_app, next_app)
                    return
                else:
                    # is a defautl scheduled app ?
                    if c_app.get('is_default', False) and self.app_is_expired(c_app):
                        print_flush('===> Stoping Default Scheduled app')
                        SchedulerState.stop_app(c_app)
                        return
                    # it's a USER_APP, we let it running, do nothing
                    else:
                        pass
        else:
            # is an user-app waiting in queue to be started ?
            if len(queue) > 0:
                start_fap.apply_async(args=[queue[0]], queue='userapp')
                print_flush("## Starting {}".format(queue[0]['name']))
                SchedulerState.pop_user_app_queue(queue)
            # start default scheduled_app
            else:
                self.start_default_app()

    def check_scheduler(self):
        if SchedulerState.get_forced_app():
            return False

        self.keep_alive_waiting_app()
        queue = SchedulerState.get_user_app_queue()
        c_app = SchedulerState.get_current_app()
        # one task already running
        now = datetime.datetime.now()
        if c_app:
            # expire soon
            if now > (datetime.datetime.strptime(c_app['expire_at'], "%Y-%m-%d %H:%M:%S.%f") - datetime.timedelta(seconds=EXPIRE_SOON_DELAY)):
                if not SchedulerState.get_expire_soon():
                    Fap.send_expires_soon(EXPIRE_SOON_DELAY)
            # expire
            # if now > (datetime.datetime.strptime(c_app['expire_at'], "%Y-%m-%d %H:%M:%S.%f")):
            #     if not SchedulerState.get_expire():
            #         Fap.send_expires()
            # Someone wait for his own task ?
            if len(queue) > 0:
                next_app = queue[0]
                if now > datetime.datetime.strptime(
                        c_app['expire_at'], "%Y-%m-%d %H:%M:%S.%f") or c_app['is_default']:
                    print_flush('===> REVOKING APP, someone else turn')
                    SchedulerState.stop_app(c_app, Fap.CODE_EXPIRE, 'someone else turn')
                    # Start app
                    start_fap.apply_async(args=[next_app], queue='userapp')
                    print_flush("## Starting {} [case A]".format(next_app['name']))
                    # Remove app form waiting Q
                    SchedulerState.pop_user_app_queue(queue)
                    return True
        else:
            # no app runing, app are waiting in queue. We start one
            if len(queue) > 0:
                start_fap.apply_async(args=[queue[0]], queue='userapp')
                print_flush("## Starting {} [case B]".format(queue[0]['name']))
                SchedulerState.pop_user_app_queue(queue)
                return True
            else:
                # No task waiting, start defautl scheduler
                default_scheduled_app = SchedulerState.get_next_default_app()
                # defualt app are schedulled, and stopped auto when expire is outdated.
                # any other app starrted by user has highter
                if default_scheduled_app:
                    next_app = {'name': default_scheduled_app.name,
                                'params': default_scheduled_app.default_params,
                                'username': '>>>default<<<',
                                'is_default': True}
                    # expires => in seconde
                    next_app['expires'] = default_scheduled_app.duration
                    if not next_app['expires'] or next_app['expires'] == 0:
                        next_app['expires'] = (15 * 60)
                    start_default_fap.apply_async(args=[next_app], queue='userapp')
                    SchedulerState.wait_task_to_start()
                    print_flush("## Starting {} [DEFAULT]".format(next_app['name']))
                    return True
        return False

    def print_scheduler_info(self):
        sleep(0.1)
        self.frontage.update()
        if self.count % 50 == 0:
            print_flush("-------- Current App")
            print_flush(SchedulerState.get_current_app())
            print_flush("-------- Enable State")
            print_flush(SchedulerState.get_enable_state())
            print_flush("-------- Usable?")
            print_flush(SchedulerState.usable())
            print_flush("Is Frontage Up?")
            print_flush(SchedulerState.is_frontage_on())
            print_flush("---------- Waiting Queue")
            print_flush(SchedulerState.get_user_app_queue())
            print_flush('Forced App ?' + str(SchedulerState.get_forced_app() == 'True'))
            print_flush("---------- Sunrise")
            print_flush(SchedulerState.get_scheduled_off_time())
            print_flush(SchedulerState.get_forced_off_time())
            print_flush("---------- Sunset")
            print_flush(SchedulerState.get_scheduled_on_time())
            print_flush(" ========== Scheduling ==========")
        self.count += 1

    def run(self):
        # last_state = False
        # we reset the value
        SchedulerState.set_frontage_on(True)
        SchedulerState.set_enable_state(SchedulerState.get_enable_state())
        # usable = SchedulerState.usable()
        print_flush('[SCHEDULER] Entering loop')
        self.frontage.start()
        self.count = 0
        while True:
            self.run_scheduler()
            self.print_scheduler_info()


def load_day_table(file_name):
    with open(file_name, 'r') as f:
        SUN_TABLE = json.loads(f.read())
        redis.set(SchedulerState.KEY_DAY_TABLE, json.dumps(SUN_TABLE))


if __name__ == '__main__':
    try:
        load_day_table(SchedulerState.CITY)
        scheduler = Scheduler(hardware=True)
        scheduler.run()
        print_flush('=== Scheduler Stop ===')
    except Exception as e:
        print_flush('=== Scheduler Exception ===')
        print_flush(e)
        print_flush('===========================')
        SENTRY.captureException()
