from threading import Thread, Event
import time
import os
import signal

def handler(signum, frame):
   raise Exception("end of time")

mesh = "mesh"
scheduler = "scheduler"
queue = "queue"
app = "app"
redis = "redis"
rabit = "rabbit"
postgres = "postgres"
# containers = [redis, rabit, postgres, mesh, scheduler, queue, app]
containers = [redis, rabit, postgres, scheduler]



def get_logs(container, file):
    os.system("docker-compose logs --tail=100 -t {0} >> {1}".format(container, file))

if __name__ == '__main__' :
    signal.signal(signal.SIGALRM, handler)
    os.system("mkdir logs")
    for container in containers :
        os.system("mkdir logs/{0}".format(container))
    num = 0
    path = "logs"
    while True :
        num += 1
        for cont in containers :
            try :
                get_logs(cont , "{0}/{1}/log_{2}".format(path, cont, num))
            except :
                pass
        time.sleep(60)
