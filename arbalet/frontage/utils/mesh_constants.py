
# Connection
HOST='0.0.0.0' #IP address to listen to. Can be set to 0.0.0.0 to listen to every request.
PORT=9988 # Port to which the server will be binded. Connection request will be done to this port.

#Software version
SOFT_VERSION = 2

#Frame's type
BEACON = 1 #Declaration frame
INSTALL = 3 #Frame which acts both as acknowledgement, and trigger to update routing table
COLOR = 4 #Frame containing colors triplet for all declared cards.
AMA = 6 #Frame related to the Addressing procedure
ERROR = 7 #Frame indicating that an error occured, or is being handled.
REBOOT = 8 #Frame to reboot all esps
LOG = 9 #Frame going upstream to the server for debug

#AMA frame subtype
AMA_INIT = 61 #Starts the AMA procedure
AMA_COLOR = 62 #Stops the AMA procedure

#ERROR frame subtype
ERROR_CO = 71 #A new connection occured within the mesh network
ERROR_DECO = 72 #A disconnection occured within the mesh network
ERROR_GOTO = 73 #Forces a card to change to the state specified in the frame.
ERROR_ROOT = 74 #Indicates that a server reconnection happened, and error procedure must be used.

#Field
VERSION = 0 #Field of the Software version
TYPE = 1 #Field of the frame type
DATA = 2 #Start of the DATA field
FRAME_SIZE = 16 #Conventionnal frame size, is true for every frame except COLOR frame.

#ESP32
MAC_SIZE = 6

#States
STATE_INIT = 1 #Declaration state
STATE_CONF = 2 #Root-exclusive state, relay node<->server declaration/acknowledgement
STATE_ADDR = 3 #State in which the addressing procedure occurs.
STATE_COLOR = 4 #Production state, main state.
STATE_ERROR = 5 #Error management state.
