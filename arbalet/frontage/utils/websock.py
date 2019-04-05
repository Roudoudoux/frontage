import asyncio
import websockets
import json

from utils.red import redis, redis_get
from threading import Thread
from server.flaskutils import print_flush

KEY_WS_SEND = "KEY_WS_SEND"
KEY_WS_SEND_MAC = "KEY_WS_SEND_MAC"
POS_UNK = "POS_UNK"
PIXELS = "PIXELS"
DECO = "DECO"
ADDR = "ADDR"
AMA = "AMA"
GET_DECO = "GET_DECO"

class Websock(Thread):
    def __init__(self, fap, host='0.0.0.0', port=9988):
        Thread.__init__(self)
        self.fap = fap
        self.host = host
        self.port = port
        self.web_socket = None

    @staticmethod
    def send_data(code, message, username='', userid=''):
        print_flush("###############################################################################")
        print_flush("Send : [code={0}] [message={1}] [username={2}] [userid={3}]".format(code, message, username, userid))
        print_flush("###############################################################################")
        redis.set(KEY_WS_SEND, json.dumps({'code': code,
                                           'message': message,
                                           'username': username,
                                           'userid': userid}))

    @staticmethod
    def send_pos_unk(pos_unknown):
        print_flush("###############################################################################")
        print_flush("Send : [pos_unknown={0}]".format(pos_unknown))
        print_flush("###############################################################################")
        redis.set(POS_UNK, json.dumps(pos_unknown))

    @staticmethod
    def send_pixels(pixels):
        print_flush("###############################################################################")
        print_flush("Send : [pixels={0}]".format(pixels))
        print_flush("###############################################################################")
        redis.set(PIXELS, json.dumps(pixels))

    @staticmethod
    def send_deco(deconnected_pixels):
        print_flush("###############################################################################")
        print_flush("Send : [pixels_deconnected={0}]".format(deconnected_pixels))
        print_flush("###############################################################################")
        redis.set(DECO, json.dumps(deconnected_pixels))

    @staticmethod
    def send_get_deco(bool=False):
        print_flush("Send : [get_deco={}]".format(bool))
        if bool :
            redis.set(GET_DECO, "True")
        else :
            redis.set(GET_DECO, 'None')

    @staticmethod
    def should_get_deco():
        data = redis_get(GET_DECO, None)
        if data:
            redis.set(GET_DECO, 'None')
        if data == 'None':
             return False
        return True

    @staticmethod
    def send_esp_state(esp_state):
        print_flush("###############################################################################")
        print_flush("Send : [esp_state = {0}]".format(esp_state))
        print_flush("###############################################################################")
        redis.set(ADDR, json.dumps(esp_state))

    @staticmethod
    def send_ama_model(ama_model):
        print_flush("###############################################################################")
        print_flush("Send : [matrix type = {0}]".format(ama_model))
        print_flush("###############################################################################")
        redis.set(AMA, json.dumps({'ama' : ama_model}))

    @staticmethod
    def get_ama_model():
        data = redis_get(AMA, None)
        if data:
            redis.set(AMA, 'None')
        if data == 'None':
             return None
        return data

    @staticmethod
    def get_esp_state():
        data = redis_get(ADDR, None)
        return data

    @staticmethod
    def get_data():
        data = redis_get(KEY_WS_SEND, None)
        if data:
            redis.set(KEY_WS_SEND, 'None')
        if data == 'None':
            return None
        return data

    @staticmethod
    def get_pos_unk():
        data = redis_get(POS_UNK, None)
        if data == 'None':
            return None
        return data

    @staticmethod
    def get_pixels():
        data = redis_get(PIXELS, None)
        if data == 'None':
            return None
        return data

    @staticmethod
    def get_deco():
        data = redis_get(DECO, None)
        if data == 'None':
            return None
        return data

    async def consumer_handler(self, websocket, path): # noqa
        while True:
            data = await websocket.recv()
            print('=====> GOT DATA' + data)
            self.fap.handle_message(data, path)

    async def producer_handler(self, websocket, path):
        while True:
            await asyncio.sleep(0.01)
            data_to_send = Websock.get_data()
            if data_to_send:
                print('=====> SEND    DATA')
                print(data_to_send)
                await websocket.send(data_to_send)

    async def handler(self, websocket, path):
        consumer_task = asyncio.ensure_future(self.consumer_handler(websocket, path))
        producer_task = asyncio.ensure_future(self.producer_handler(websocket, path))
        done, pending = await asyncio.wait(
            [consumer_task, producer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

    def run(self):
        print('=====> Run Websock')
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.web_socket = websockets.serve(self.handler, self.host, self.port)

        asyncio.get_event_loop().run_until_complete(self.web_socket)
        asyncio.get_event_loop().run_forever()
        print('=====> Close Websock')

    def close(self):
        print_flush('====== CLOSE WEBSOCKET NICELY /1 =========')
        self.web_socket.ws_server.close()
