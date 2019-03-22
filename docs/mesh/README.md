Introduction 
============

The Arbalet Mesh project is composed of a server and *n* ESP32 part of a
mesh network.

The server is hosted on a WiFi network protected by WPA2 protocol on
which the ESP32 Root will connect.

The esp-idf framework implements a tree-shape mesh network which links
the ESP32 together through a WiFi protocol. The tree root is the only
ESP32 able to connect itself on an external WiFi network.

The Arbalet Mesh project application layer uses the following
communications protocol (based on 9 frames and a finite-state machine)
for the message transmissions.

Frames
======

Frame composition
-----------------

In the mesh network, all frames are 16 Bytes long and share a common
pattern (e.g FIGURE [1](#fig:Meshframe)) but one which is the frame **COLOR**.
**COLOR** is only transmitted from the Server to the ESP32 Root and will
be described . The frame Bytes use the *uint8\_t* type.

![Frame format in mesh
network[]{label="fig:Meshframe"}](images/img/MeshFrame.png)

-   The first Byte is the software version. If the software version
    within the frame does not correspond with the one hard-coded in the
    ESP32, the frame is ignored.

-   The second Byte is the frame type. The type determines how the frame
    will be handled by the ESP32.

-   The next 12 Bytes contains the data. The data format depends on the
    frame type.

-   The last Bytes are a check-sum. If the check-sum does not match the
    frame is ignored.

Software Version
----------------

Python server and the ESP32 have a global variable hard-coded - named
**VERSION** - which corresponds to their respective software version.

To ensure that frames are correctly handled, the sender's **VERSION** is
communicated in each message and compared with the receiver's one. If
the versions match the frame is handled, else an error is raised and the
pixels flash in red.

Check-sum
---------

The application protocol has a light check-sum which ensures that frames
are not corrupted. This check-sum is based on the frame bits parity. A
parity bit is computed on 7 bits as shown in the FIGURE
[2](#fig:Checksum). The
check-sum is put at the frame's end. The check-sum length ![equation](https://latex.codecogs.com/gif.latex?%24cs_%7Blen%7D%24) is
related to the frame length ![equation](https://latex.codecogs.com/gif.latex?%24f_%7Blen%7D%24) by the relation
![equation](https://latex.codecogs.com/gif.latex?sc_%7Blen%7D%20%3D%20%5Clceil%20%5Cfrac%7Bf_%7Blen%7D%7D%7B8%7D%20%5Crceil).

![Example of computed
check-sum[]{label="fig:Checksum"}](images/img/Check-sum.png)

Frame types
-----------

### BEACON

**Type :** 1\
**Communication :** ESP32 -> ESP32 Root, ESP32 Root -> Server\
**Frame length :** 16 Bytes\
**Byte type :** *uint8\_t*

BEACON frames are the first ones to be emitted on the mesh network. When
an ESP32 integrates the mesh network, it transmits a BEACON frame to the
ESP32 Root which relays it to the server.\
As long as the BEACON is not acknowledge by the ESP32 Root, the ESP32
keeps emitting it.

![Beacon data[]{label="fig:beacon"}](images/img/BEACON.png)

### BEACON\_ACK

**Type :** 2\
**Communication :** ESP32 Root -> ESP32\
**Frame length :** 16 Bytes\
**Byte type :** *uint8\_t*

BEACON\_ACK frame is sent by the ESP32 Root to an ESP32 as a BEACON
acknowledgement. The ESP32 Root emits this frame only when it has
received the corresponding INSTALL frame form the server. A flag is
raised if the ESP32 has declared itself outside of the declaration
phase.

![Beacon\_ack
data[]{label="fig:beacona"}](images/img/BEACONA.png)

### INSTALL

**Type :** 3\
**Communication :** Server -> ESP32 Root\
**Frame length :** 16 Bytes\
**Byte type :** *uint8\_t*

INSTALL frames are transmitted from the server to the ESP32 Root. It is
an acknowledgement of a previous BEACON frame received by the server and
it fixes the MAC address position in the *route\_table* of the ESP32
Root.

![Install
data[]{label="fig:install"}](images/img/INSTALL.png)

### COLOR

**Type :** 4\
**Communication :** Server -> ESP32 Root\
**Frame length :**
![equation](https://latex.codecogs.com/gif.latex?%5Clceil%20%5Cfrac%7B8%20%5Ctimes%20%284%20&plus;%20pixel%5C%20amount%20%5Ctimes%203%29%7D%7B7%7D%20%5Crceil) Bytes\
**Byte type :** *uint8\_t*

The **COLOR** frame transmits from the Server to the ESP32 Root an array
which contains all the color (in RGB format) the mesh network has to
display. Moreover, it also contains a version number (1 Byte), its frame
type (1 Byte), a sequence number (2 Bytes) and a check-sum
(![equation](https://latex.codecogs.com/gif.latex?%5Clceil%20%5Cfrac%7Bframe_length%7D%7B8%7D%5Crceil) Bytes).

![COLOR data[]{label="fig:color"}](images/img/COLOR.png)

The ESP32 Root compares the frame sequence number (*seq*) with the last
one it received (*local\_seq*). If *seq* is higher than *local\_seq*,
the frame is considered as valid and *local\_seq* gets *seq* value.
Otherwise the frame is rejected for it is a late frame with no use
anymore.

### COLOR\_E

**Type :** 5\
**Communication :** ESP32 Root -> ESP32\
**Frame length :** 16 Bytes\
**Byte type :** *uint8\_t*

A COLOR\_E frame contains the color which is to be displayed by the
ESP32.

![COLOR\_E
data[]{label="fig:color-e"}](images/img/COLOR-E.png)

The receiver ESP32 compares the frame sequence number (*seq*) with the
last one it received (*local\_seq*). If *seq* is higher than
*local\_seq*, the frame is considered as valid and *local\_seq* gets
*seq* value. Otherwise the frame is rejected for it is a late frame with
no use anymore.

### AMA

**Type :** 6\
**Communication :** ESP32 ![equation](https://latex.codecogs.com/gif.latex?%3C-%3E) ESP32, Server -> ESP32 Root\
**Frame length :** 16 Bytes\
**Byte type :** *uint8\_t*

AMA frames are sent from the server to the mesh network. It starts and
ends the assisted manual addressing on administrator command.

![AMA data[]{label="fig:ama"}](images/img/AMA.png)

**AMA** frame has 3 sub-types :

-   **AMA\_init** : code 61, is sent from the server to the ESP32 Root.
    Starts the **AMA** process.

-   **AMA\_color** : code 62, is broadcast on the mesh network. Ends the
    **AMA** process.

### ERROR

**Type :** 7\
**Communication :** ESP32 ![equation](https://latex.codecogs.com/gif.latex?%3C-%3E) ESP32, ESP32 Root ![equation](https://latex.codecogs.com/gif.latex?%3C-%3E) Server\
**Frame length :** 16 Bytes\
**Byte type :** *uint8\_t*

ERROR frames are used to handle exceptions and mesh connection problems.
The flag section is used to acknowledge the frame received and to
transmit the sender state. The ![equation](https://latex.codecogs.com/gif.latex?%247%5E%7Bth%7D%24) bit is an acknowledgement bit,
the ![equation](https://latex.codecogs.com/gif.latex?%245%5E%7Bth%7D%24) bit is dedicated to determine if there is any ESP32 which
physical position is unknown, the first four bits represent the previous
state of the sender, and other bits are currently unused.

![ERROR Data[]{label="fig:error"}](images/img/ERROR.png)

-   **ERROR\_co** : code 71, is a frame sent from the ESP32 Root to the
    server whenever a new ESP32 is connected. Its sub-type incurs an
    acknowledgement frame.

-   **ERROR\_deco** : code 72, is a frame sent from the ESP32 Root to
    the server whenever an ESP32 is disconnected. Its sub-type incurs an
    acknowledgement frame.

-   **ERROR\_goto** : code 73, is a special frame which puts the
    receiver ESP32 in the indicated state.

-   **ERROR\_root** : code 74, is a frame sent only if a root reelection
    has occurred in the mesh network. The new root sends its frame to
    the server to receive from it the routing table.

State machine
=============

Principle
---------

The code embarked on ESP32 is implemented as a finite-state machine
composed of 5 distinct states which are **INIT**, **CONF**, **ADDR**,
**COLOR** and **ERROR**. Transitions from one state to another occur
when particular frames are received (e.g. FIGURE
[10](#fig:statemachine) & [11](#fig:Nodes)).

![State machine used by ESP32
Nodes[]{label="fig:Nodes"}](images/img/StateMachine.png)

![State machine used by ESP32
Nodes[]{label="fig:Nodes"}](images/img/NODES.png)

Pixels are in operating mode when they are in **COLOR** state. All the
ESP32 embarks the full state machine (FIGURE
[10](#fig:statemachine) but the **CONF** state is only accessible
to the ESP32 Root. Although ESP32 Nodes are allowed in a restricted area
(FIGURE [11](#fig:Nodes)),
they embarks the full state machine instead of a lighter version because
the ESP32 Root is not determined and any Node card can become Root if an
error occurs.

States
------

Some behaviours are the same for all cards. In all states :

-   An ERROR\_goto(state) frame can be received, and the card will
    switch to the indicated state.

-   ERROR frames can be received and processed, were an error to
    happened.

Then, each state has its own behaviour.

### INIT

The INIT state is the starting state of the cards, in which they
initialise their variables, and declare themselves to the corresponding
networks.

-   Root card :

    -   The Root card sends a BEACON frame to the server. It repeats
        this step until it receives an acknowledgement.

    -   On reception of an INSTALL frame from the server, the card will
        update its routing table, and will switch into the CONF state.

-   Node cards :

    -   The Node cards send a BEACON frame to the root card. They repeat
        this step until it receive acknowledgement.

    -   On reception of a BEACON\_ACK frame from the root card, the
        cards will switch into the ADDR state.

    -   Cards can also receive a BEACON\_ACK frame with error flag
        raised, indicating that the mesh network is already running, and
        the error protocol must be used to address this card.

### CONF

The CONF state is only available for the root card. In this state, it
will relay the BEACON frame received from the mesh network to the
server, and the server response to the concerned cards.

-   On reception of a BEACON frame, the root card will relay it as it is
    to the server.

-   On reception of a INSTALL frame, the card will update its routing
    table, and send a BEACON\_ACK frame to the concerned card, using the
    MAC address contained in the INSTALL frame.

-   On reception of an AMA\_init frame, the card will switch into the
    ADDR state.

### ADDR

The ADDR state is used to do the Assisted Manual Addressing, in order to
associate each card with a pixel of the image matrix.

-   On reception of a COLOR frame from the server, the root card will
    break it into COLOR\_E frame, and send them to the proper cards
    according to its routing table.

-   On reception of a COLOR\_E frame, the card will display the color
    contained in the frame.

-   On reception of an INSTALL frame, the card will update its routing
    table. If it is the root card, it will broadcast it to the mesh
    network.

-   On reception of an AMA\_color frame, the card will switch into the
    COLOR state. If it is the root card, it will broadcast it to the
    mesh network.

-   Reception of a BEACON frame is indicator that an error occurred and
    a card has been reset, as such, the root card will switch into the
    ERROR state to process the trouble.

-   If a card is disconnected, the root card will switch into the ERROR
    state to process the trouble.

### COLOR

The COLOR state is the main state of the cards, in which they display
the image sent from the server.

-   On reception of a COLOR frame from the server, the root card will
    break it into COLOR\_E frame, and send them to the proper cards
    according to its routing table.

-   On reception of a COLOR\_E frame, the card will display the color
    contained in the frame.

-   Reception of a BEACON frame is indicator that an error occurred and
    a card has been reset, as such, the root card will switch into the
    ERROR state to process the trouble.

-   If a card is disconnected, the root card will switch into the ERROR
    state to process the trouble.

### ERROR

This state indicate that an error occurred while the mesh network was
running, and correction must be applied. This state possesses the same
interactions as the COLOR state, with exclusive behaviour used in the
following cases :

-   A card has been disconnected from the network, either gracefully
    (software error) or not (hardware error) : the Root card switches to
    the ERROR state, and mark the card has unreachable in its routing
    table.

    -   The Root card sends a ERROR\_deco frame to the server, to report
        the incident.

    -   Once the server has acknowledged the incident, it sends back a
        ERROR\_deco frame, with the ACK flag raised. The Root then
        switches back to the COLOR state

    A previously disconnected card is reconnected to the network

    -   The Root card sends a ERROR\_co frame to the server, with the
        newly declared MAC address.

    -   The server recognises this card, and sends back a ERROR\_co,
        with the ACK flag raised : the Root card marks the card as
        reachable in its routing table, and acknowledge the card with a
        BEACON\_ACK frame. Finally, if it is not blocked, it switches
        back to the COLOR state.

    A new card is connected to the network.

    -   The Root card sends a ERROR\_co frame to the server, with the
        newly declared MAC address.

    -   The server considers it as an unadressed card : it sends back a
        ERROR\_co frame, with both the ACK and UNK flag raised. The Root
        card acknowledges the card with a BEACON\_ACK frame with error
        flag raised, and locks itself in ERROR state.

    On reception of a ERROR\_goto(CONF), the Root card will switch to
    the CONF state, in order to address all the new cards. Then, the
    standard Addressing procedure will be followed.
