# The program implements a simple controller for a network with 6 hosts and 5 switches.
# The switches are connected in a diamond topology (without vertical links):
#    - 3 hosts are connected to the left (s1) and 3 to the right (s5) edge of the diamond.
# Overall operation of the controller:
#    - default routing is set in all switches on the reception of packet_in messages form the switch,
#    - then the routing for (h1-h4) pair in switch s1 is changed every one second in a round-robin manner to load balance the traffic through switches s3, s4, s2.

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpidToStr
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.packet.arp import arp
from pox.lib.packet.ethernet import ethernet, ETHER_BROADCAST
from pox.lib.packet.packet_base import packet_base
from pox.lib.packet.packet_utils import *
import pox.lib.packet as pkt
from pox.lib.recoco import Timer
import time
from operator import itemgetter

# S1-S2 link measurements
s1s2_start_time = 0.0
s1s2_sent_time2 = 0.0
s1s2_OWD2 = 0.0
s1s2_delay_link = 0.0

# S1-S3 link measurements
s1s3_start_time = 0.0
s1s3_sent_time2 = 0.0
s1s3_OWD2 = 0.0
s1s3_delay_link = 0.0

# S1-S4 link measurements
s1s4_start_time = 0.0
s1s4_sent_time2 = 0.0
s1s4_OWD2 = 0.0
s1s4_delay_link = 0.0

OWD1_send_time = 0.0
OWD1_receive_time = 0.0

log = core.getLogger()

s1_dpid = 0
s2_dpid = 0
s3_dpid = 0
s4_dpid = 0
s5_dpid = 0

s1_p4 = 0
s1_p5 = 0
s1_p6 = 0
pre_s1_p4 = 0
pre_s1_p5 = 0
pre_s1_p6 = 0

start_time = 0
turn = 0

default_route_s1 = 4
default_route_s5 = 1

current_delays = []
current_flows = {'s2': 0, 's3': 0, 's4': 0}
current_routing = []
# example routing: {'intent': intent, 'path': 4}
# paths: s2 - 4; s3 - 5; s4 - 6

intents = []
other_intents = []

# testing intents
intents.append({'source': 'h1',
                'destination': 'h4',
                'delay': 90.0})
intents.append({'source': 'h1',
                'destination': 'h5',
                'delay': 90.0})
intents.append({'source': 'h1',
                'destination': 'h6',
                'delay': 20.0})
intents.append({'source': 'h2',
                'destination': 'h4',
                'delay': 600.0})
intents.append({'source': 'h2',
                'destination': 'h5',
                'delay': 50.0})
intents.append({'source': 'h2',
                'destination': 'h6',
                'delay': 150.0})

def modify_flow(src, dst, output_switch):
    src_ip_addr = None
    if src == 'h1':
        src_ip_addr = "10.0.0.1"
    elif src == 'h2':
        src_ip_addr = "10.0.0.2"
    elif src == 'h3':
        src_ip_addr = "10.0.0.3"

    dst_ip_addr = None
    if dst == 'h4':
        dst_ip_addr = "10.0.0.4"
    elif dst == 'h5':
        dst_ip_addr = "10.0.0.5"
    elif dst == 'h6':
        dst_ip_addr = "10.0.0.6"

    output_port1 = None
    output_port2 = None
    if output_switch == 's2':
        output_port1 = 4
        output_port2 = 1
    elif output_switch == 's3':
        output_port1 = 5
        output_port2 = 2
    elif output_switch == 's4':
        output_port1 = 6
        output_port2 = 3

    msg = of.ofp_flow_mod()
    msg.command = of.OFPFC_MODIFY_STRICT
    msg.priority = 100
    msg.idle_timeout = 0
    msg.hard_timeout = 0
    msg.match.dl_type = 0x0800
    msg.match.nw_src = IPAddr(src_ip_addr)
    msg.match.nw_dst = IPAddr(dst_ip_addr)
    msg.actions.append(of.ofp_action_output(port = output_port1))
    core.openflow.getConnection(s1_dpid).send(msg)

    msg = of.ofp_flow_mod()
    msg.command = of.OFPFC_MODIFY_STRICT
    msg.priority = 100
    msg.idle_timeout = 0
    msg.hard_timeout = 0
    msg.match.dl_type = 0x0800
    msg.match.nw_src = IPAddr(dst_ip_addr)
    msg.match.nw_dst = IPAddr(src_ip_addr)
    msg.actions.append(of.ofp_action_output(port=output_port2))
    core.openflow.getConnection(s5_dpid).send(msg)


def delete_flow(route):
    src = route['intent']['source']
    src_ip_addr = None
    if src == 'h1':
        src_ip_addr = "10.0.0.1"
    elif src == 'h2':
        src_ip_addr = "10.0.0.2"
    elif src == 'h3':
        src_ip_addr = "10.0.0.3"

    dst = route['intent']['destination']
    dst_ip_addr = None
    if dst == 'h4':
        dst_ip_addr = "10.0.0.4"
    elif dst == 'h5':
        dst_ip_addr = "10.0.0.5"
    elif dst == 'h6':
        dst_ip_addr = "10.0.0.6"

    output_switch = route['path']
    output_port1 = None
    output_port2 = None
    if output_switch == 's2':
        output_port1 = 4
        output_port2 = 1
    elif output_switch == 's3':
        output_port1 = 5
        output_port2 = 2
    elif output_switch == 's4':
        output_port1 = 6
        output_port2 = 3

    msg = of.ofp_flow_mod()
    msg.command = of.OFPFC_DELETE_STRICT
    msg.priority = 100
    msg.idle_timeout = 0
    msg.hard_timeout = 0
    msg.match.dl_type = 0x0800
    msg.match.nw_src = IPAddr(src_ip_addr)
    msg.match.nw_dst = IPAddr(dst_ip_addr)
    msg.actions.append(of.ofp_action_output(port=output_port1))
    core.openflow.getConnection(s1_dpid).send(msg)

    msg = of.ofp_flow_mod()
    msg.command = of.OFPFC_DELETE_STRICT
    msg.priority = 100
    msg.idle_timeout = 0
    msg.hard_timeout = 0
    msg.match.dl_type = 0x0800
    msg.match.nw_src = IPAddr(dst_ip_addr)
    msg.match.nw_dst = IPAddr(src_ip_addr)
    msg.actions.append(of.ofp_action_output(port=output_port2))
    core.openflow.getConnection(s5_dpid).send(msg)


def intent_routing():
    global intents, current_routing, s1s2_delay_link, s1s3_delay_link, s1s4_delay_link
    global default_route_s1, default_route_s5, current_flows, other_intents, current_delays

    new_current_routing = []
    new_current_flows = {'s2': 0, 's3': 0, 's4': 0}
    delays = []
    delays.append({'path': 's2', 'delay': s1s2_delay_link})
    delays.append({'path': 's3', 'delay': s1s3_delay_link})
    delays.append({'path': 's4', 'delay': s1s4_delay_link})

    delays = sorted(delays, key=itemgetter('delay'), reverse=True)
    current_delays = delays
    intents = sorted(intents, key=itemgetter('delay'))

    for intent in intents:
        optimal_path = None
        possible_path = []
        for x, delay in enumerate(delays):
            if delay['delay'] < intent['delay']:
                possible_path.append(delay)
            if x + 1 == len(delays) and possible_path == []:
                optimal_path = delay['path']
                new_current_flows[optimal_path] += 1
                new_current_routing.append({'intent': intent, 'path': optimal_path})
                break
        if possible_path != []:
            possible_path = sorted(possible_path, key=itemgetter('delay'), reverse=True)
            best_path_flows = None
            for x, path in enumerate(possible_path):
                if x == 0 or new_current_flows[path['path']] <= best_path_flows:
                    best_path_flows = new_current_flows[path['path']]
                    optimal_path = path['path']
            new_current_flows[optimal_path] += 1
            new_current_routing.append({'intent': intent, 'path': optimal_path})

    for flow in other_intents:
        best_path_flows = None
        optimal_path = None
        for x, delay in enumerate(delays):
            if x == 0 or new_current_flows[delay['path']] <= best_path_flows:
                best_path_flows = new_current_flows[delay['path']]
                optimal_path = delay['path']
        new_current_flows[optimal_path] += 1
        new_current_routing.append({'intent': flow, 'path': optimal_path})

    for new_route in new_current_routing:
        old_route_found = False
        for route in current_routing:
            if route['intent'] == new_route['intent']:
                if route['path'] != new_route['path']:
                    print "Changed routing path for intent: ", new_route
                    print "Changed path: ", new_route['path']
                    modify_flow(new_route['intent']['source'], new_route['intent']['destination'], new_route['path'])
                old_route_found = True
                break
        if old_route_found is False:
            print "New routing path for intent: ", new_route
            print "New path: ", new_route['path']
            modify_flow(new_route['intent']['source'], new_route['intent']['destination'], new_route['path'])

    current_routing = new_current_routing
    current_flows = new_current_flows
    print "\nCurrent flows: S2: ", current_flows['s2'], "; S3: ", current_flows['s3'], "; S4: ", current_flows['s4']
    print "Current routing: "
    for routing in current_routing:
        print routing
    print "\n"

    if delays[-1]['path'] == 's2':
        default_route_s1 = 4
        default_route_s5 = 1
    elif delays[-1]['path'] == 's3':
        default_route_s1 = 5
        default_route_s5 = 2
    elif delays[-1]['path'] == 's4':
        default_route_s1 = 6
        default_route_s5 = 3


#probe protocol packet definition; only timestamp field is present in the header (no payload part)
class myproto(packet_base):
    #My Protocol packet struct
    """
    myproto class defines our special type of packet to be sent all the way along including the link between the switches to measure link delays;
    it adds member attribute named timestamp to carry packet creation/sending time by the controller, and defines the
    function hdr() to return the header of measurement packet (header will contain timestamp)
    """
    #For more info on packet_base class refer to file pox/lib/packet/packet_base.py

    def __init__(self):
        packet_base.__init__(self)
        self.timestamp=0

    def hdr(self, payload):
        return struct.pack('!I', self.timestamp) # code as unsigned int (I), network byte order (!, big-endian - the most significant byte of a word at the smallest memory address)


def getTheTime():  # function to create a timestamp
    flock = time.localtime()
    then = "[%s-%s-%s" % (str(flock.tm_year), str(flock.tm_mon), str(flock.tm_mday))

    if int(flock.tm_hour) < 10:
        hrs = "0%s" % (str(flock.tm_hour))
    else:
        hrs = str(flock.tm_hour)
    if int(flock.tm_min) < 10:
        mins = "0%s" % (str(flock.tm_min))
    else:
        mins = str(flock.tm_min)

    if int(flock.tm_sec) < 10:
        secs = "0%s" % (str(flock.tm_sec))
    else:
        secs = str(flock.tm_sec)

    then += "]%s.%s.%s" % (hrs, mins, secs)
    return then


def _timer_func():
    global s1_dpid, start_time, turn, first_iter, OWD1_send_time

    # measuring S1-S2 link
    global s1s2_sent_time2, s2_dpid

    # the following executes only when a connection to 'switch0' exists (otherwise AttributeError can be raised)
    if s1_dpid <> 0 and not core.openflow.getConnection(s1_dpid) is None and turn == 0:
        # send out port_stats_request packet through switch0 connection src_dpid (to measure T1)
        core.openflow.getConnection(s1_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
        OWD1_send_time = time.time() * 1000 * 10 - start_time  # sending time of stats_req: ctrl => switch0
        # print "sent_time1:", s1s2_sent_time1

        # sequence of packet formating operations optimised to reduce the delay variation of e-2-e measurements (to measure T3)
        f = myproto()  # create a probe packet object
        e = pkt.ethernet()  # create L2 type packet (frame) object
        e.src = EthAddr("0:0:0:0:0:2")
        e.dst = EthAddr("0:1:0:0:0:1")
        e.type = 0x5577  # set unregistered EtherType in L2 header type field, here assigned to the probe packet type
        msg = of.ofp_packet_out()  # create PACKET_OUT message object
        msg.actions.append(of.ofp_action_output(port=4))  # set the output port for the packet in switch0
        f.timestamp = int(time.time() * 1000 * 10 - start_time) # set the timestamp in the probe packet
        # print f.timestamp
        e.payload = f
        msg.data = e.pack()
        core.openflow.getConnection(s1_dpid).send(msg)
        #print "=====> S1-S2 probe sent: f=", f.timestamp, " after=", int(time.time() * 1000 * 10 - start_time), " [10*ms]"

    # the following executes only when a connection to 'switch1' exists (otherwise AttributeError can be raised)
    if s2_dpid <> 0 and not core.openflow.getConnection(s2_dpid) is None and turn == 0:
        # send out port_stats_request packet through switch1 connection dst_dpid (to measure T2)
        core.openflow.getConnection(s2_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
        s1s2_sent_time2 = time.time() * 1000 * 10 - start_time  # sending time of stats_req: ctrl => switch1
        # print "sent_time2:", sent_time2

    # measuring S1-S3 link
    global s1s3_sent_time2, s3_dpid

    # the following executes only when a connection to 'switch0' exists (otherwise AttributeError can be raised)
    if s1_dpid <> 0 and not core.openflow.getConnection(s1_dpid) is None and turn == 1:
        # send out port_stats_request packet through switch0 connection src_dpid (to measure T1)
        core.openflow.getConnection(s1_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
        OWD1_send_time = time.time() * 1000 * 10 - start_time  # sending time of stats_req: ctrl => switch0
        # print "sent_time1:", sent_time1
        # sequence of packet formating operations optimised to reduce the delay variation of e-2-e measurements (to measure T3)
        f = myproto()  # create a probe packet object
        e = pkt.ethernet()  # create L2 type packet (frame) object
        e.src = EthAddr("0:0:0:0:0:2")
        e.dst = EthAddr("0:1:0:0:0:1")
        e.type = 0x5577  # set unregistered EtherType in L2 header type field, here assigned to the probe packet type
        msg = of.ofp_packet_out()  # create PACKET_OUT message object
        msg.actions.append(of.ofp_action_output(port=5))  # set the output port for the packet in switch0
        f.timestamp = int(time.time() * 1000 * 10 - start_time)  # set the timestamp in the probe packet
        # print f.timestamp
        e.payload = f
        msg.data = e.pack()
        core.openflow.getConnection(s1_dpid).send(msg)
        #print "=====> S1-S3 probe sent: f=", f.timestamp, " after=", int(time.time() * 1000 * 10 - start_time), " [10*ms]"

    # the following executes only when a connection to 'switch1' exists (otherwise AttributeError can be raised)
    if s3_dpid <> 0 and not core.openflow.getConnection(s3_dpid) is None and turn == 1:
        # send out port_stats_request packet through switch1 connection dst_dpid (to measure T2)
        core.openflow.getConnection(s3_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
        s1s3_sent_time2 = time.time() * 1000 * 10 - start_time  # sending time of stats_req: ctrl => switch1
        # print "sent_time2:", sent_time2

    # measuring S1-S4 link
    global s1s4_sent_time2, s4_dpid

    # the following executes only when a connection to 'switch0' exists (otherwise AttributeError can be raised)
    if s1_dpid <> 0 and not core.openflow.getConnection(s1_dpid) is None and turn == 2:
        # send out port_stats_request packet through switch0 connection src_dpid (to measure T1)
        core.openflow.getConnection(s1_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
        OWD1_send_time = time.time() * 1000 * 10 - start_time  # sending time of stats_req: ctrl => switch0
        # print "sent_time1:", sent_time1
        # sequence of packet formating operations optimised to reduce the delay variation of e-2-e measurements (to measure T3)
        f = myproto()  # create a probe packet object
        e = pkt.ethernet()  # create L2 type packet (frame) object
        e.src = EthAddr("0:0:0:0:0:2")
        e.dst = EthAddr("0:1:0:0:0:1")
        e.type = 0x5577  # set unregistered EtherType in L2 header type field, here assigned to the probe packet type
        msg = of.ofp_packet_out()  # create PACKET_OUT message object
        msg.actions.append(of.ofp_action_output(port=6))  # set the output port for the packet in switch0
        f.timestamp = int(time.time() * 1000 * 10 - start_time)  # set the timestamp in the probe packet
        # print f.timestamp
        e.payload = f
        msg.data = e.pack()
        core.openflow.getConnection(s1_dpid).send(msg)
        #print "=====> S1-S4 probe sent: f=", f.timestamp, " after=", int(time.time() * 1000 * 10 - start_time), " [10*ms]"

    # the following executes only when a connection to 'switch1' exists (otherwise AttributeError can be raised)
    if s4_dpid <> 0 and not core.openflow.getConnection(s4_dpid) is None and turn == 2:
        # send out port_stats_request packet through switch1 connection dst_dpid (to measure T2)
        core.openflow.getConnection(s4_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
        s1s4_sent_time2 = time.time() * 1000 * 10 - start_time  # sending time of stats_req: ctrl => switch1
        # print "sent_time2:", sent_time2

    if turn == 3:
        intent_routing()

    if turn != 3:
        turn += 1
    else:
        turn = 0


def _handle_portstats_received(event):
    # Observe the handling of port statistics provided by this function.
    global s1_dpid, start_time, OWD1_send_time, OWD1_receive_time
    received_time = time.time() * 1000 * 10 - start_time

    # measure T1 as of lab guide
    if event.connection.dpid == s1_dpid:
        OWD1_receive_time = 0.5 * (received_time - OWD1_send_time)
        # print "OWD1: ", OWD1_send_time, "ms"

    # measuring S1-S2 link
    global s1s2_sent_time2, s2_dpid, s1s2_OWD2

    # measure T2 as of lab guide
    if event.connection.dpid == s2_dpid:
        s1s2_OWD2 = 0.5 * (received_time - s1s2_sent_time2)  # originally sent_time1 was here
        # print "OWD2: ", OWD2, "ms"

    # measuring S1-S3 link
    global s1s3_sent_time2, s3_dpid, s1s3_OWD2

    # measure T2 as of lab guide
    if event.connection.dpid == s3_dpid:
        s1s3_OWD2 = 0.5 * (received_time - s1s3_sent_time2)  # originally sent_time1 was here
        # print "OWD2: ", OWD2, "ms"

    # measuring S1-S4 link
    global s1s4_sent_time2, s4_dpid, s1s4_OWD2

    # measure T2 as of lab guide
    if event.connection.dpid == s4_dpid:
        s1s4_OWD2 = 0.5 * (received_time - s1s4_sent_time2)  # originally sent_time1 was here
        # print "OWD2: ", OWD2, "ms"

    global s1_p1, s1_p4, s1_p5, s1_p6, s2_p1, s3_p1, s4_p1
    global pre_s1_p1, pre_s1_p4, pre_s1_p5, pre_s1_p6, pre_s2_p1, pre_s3_p1, pre_s4_p1

    if event.connection.dpid == s1_dpid:  # The DPID of one of the switches involved in the link
        for f in event.stats:
            if int(f.port_no) < 65534:
                if f.port_no == 4:
                    pre_s1_p4 = s1_p4
                    s1_p4 = f.tx_packets
                    # print "s1_p4->","TxDrop:", f.tx_dropped,"RxDrop:",f.rx_dropped,"TxErr:",f.tx_errors,"CRC:",f.rx_crc_err,"Coll:",f.collisions,"Tx:",f.tx_packets,"Rx:",f.rx_packets
                if f.port_no == 5:
                    pre_s1_p5 = s1_p5
                    s1_p5 = f.tx_packets
                if f.port_no == 6:
                    pre_s1_p6 = s1_p6
                    s1_p6 = f.tx_packets


def _handle_ConnectionUp(event):
    # waits for connections from all switches, after connecting to all of them it starts a round robin timer for triggering h1-h4 routing changes
    global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid
    print
    "ConnectionUp: ", dpidToStr(event.connection.dpid)

    # remember the connection dpid for the switch
    for m in event.connection.features.ports:
        if m.name == "s1-eth1":
            # s1_dpid: the DPID (datapath ID) of switch s1;
            s1_dpid = event.connection.dpid
            print "s1_dpid=", s1_dpid
        elif m.name == "s2-eth1":
            s2_dpid = event.connection.dpid
            print "s2_dpid=", s2_dpid
        elif m.name == "s3-eth1":
            s3_dpid = event.connection.dpid
            print "s3_dpid=", s3_dpid
        elif m.name == "s4-eth1":
            s4_dpid = event.connection.dpid
            print "s4_dpid=", s4_dpid
        elif m.name == "s5-eth1":
            s5_dpid = event.connection.dpid
            print "s5_dpid=", s5_dpid

    # start 1-second recurring loop timer for round-robin routing changes; _timer_func is to be called on timer expiration to change the flow entry in s1
    if s1_dpid <> 0 and s2_dpid <> 0 and s3_dpid <> 0 and s4_dpid <> 0 and s5_dpid <> 0:
        Timer(1, _timer_func, recurring=True)


def _handle_PacketIn(event):
    global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid, start_time, OWD1_receive_time

    packet = event.parsed
    # print "_handle_PacketIn is called, packet.type:", packet.type, " event.connection.dpid:", event.connection.dpid
    received_time = time.time() * 1000 * 10 - start_time  # amount of time elapsed from start_time

    # measuring S1-S2 link
    global s1s2_OWD2, s1s2_delay_link

    if packet.type == 0x5577 and event.connection.dpid == s2_dpid:  # 0x5577 is unregistered EtherType, here assigned to probe packets
        # Process a probe packet received in PACKET_IN message from 'switch1' (dst_dpid), previously sent to 'switch0' (src_dpid) in PACKET_OUT.

        c = packet.find('ethernet').payload
        d, = struct.unpack('!I', c)  # note that d,=... is a struct.unpack and always returns a tuple
        #print "[ms*10]: received_time=", int(received_time), ", d=", d, ", OWD1=", int(OWD1_send_time), ", OWD2=", int(s1s2_OWD2)
        s1s2_delay_link = int(received_time - d - OWD1_receive_time - s1s2_OWD2) / 10
        print "S1-S2 link delay:", s1s2_delay_link, "[ms]"  # divide by 10 to normalise to milliseconds

    # measuring S1-S3 link
    global s1s3_OWD2, s1s3_delay_link

    if packet.type == 0x5577 and event.connection.dpid == s3_dpid:  # 0x5577 is unregistered EtherType, here assigned to probe packets
        # Process a probe packet received in PACKET_IN message from 'switch1' (dst_dpid), previously sent to 'switch0' (src_dpid) in PACKET_OUT.

        c = packet.find('ethernet').payload
        d, = struct.unpack('!I', c)  # note that d,=... is a struct.unpack and always returns a tuple
        #print "[ms*10]: received_time=", int(received_time), ", d=", d, ", OWD1=", int(OWD1_send_time), ", OWD2=", int(s1s3_OWD2)
        s1s3_delay_link = int(received_time - d - OWD1_receive_time - s1s3_OWD2) / 10
        print "S1-S3 link delay:", s1s3_delay_link, "[ms]"  # divide by 10 to normalise to milliseconds

    # measuring S1-S4 link
    global s1s4_OWD2, s1s4_delay_link

    if packet.type == 0x5577 and event.connection.dpid == s4_dpid:  # 0x5577 is unregistered EtherType, here assigned to probe packets
        # Process a probe packet received in PACKET_IN message from 'switch1' (dst_dpid), previously sent to 'switch0' (src_dpid) in PACKET_OUT.

        c = packet.find('ethernet').payload
        d, = struct.unpack('!I', c)  # note that d,=... is a struct.unpack and always returns a tuple
        #print "[ms*10]: received_time=", int(received_time), ", d=", d, ", OWD1=", int(OWD1_send_time), ", OWD2=", int(s1s4_OWD2)
        s1s4_delay_link = int(received_time - d - OWD1_receive_time - s1s4_OWD2) / 10
        print "S1-S4 link delay:", s1s4_delay_link, "[ms]"  # divide by 10 to normalise to milliseconds


    # Below, set the default/initial routing rules for all switches and ports.
    # All rules are set up in a given switch on packet_in event received from the switch which means no flow entry has been found in the flow table.
    # This setting up may happen either at the very first pactet being sent or after flow entry expirationn inn the switch

    if event.connection.dpid == s1_dpid:
        a = packet.find('arp')  # If packet object does not encapsulate a packet of the type indicated, find() returns None
        if a and a.protodst == "10.0.0.4":
            msg = of.ofp_packet_out(data=event.ofp)  # Create packet_out message; use the incoming packet as the data for the packet out
            msg.actions.append(of.ofp_action_output(port=default_route_s1))  # Add an action to send to the specified port
            event.connection.send(msg)  # Send message to switch

        if a and a.protodst == "10.0.0.5":
            msg = of.ofp_packet_out(data=event.ofp)
            msg.actions.append(of.ofp_action_output(port=default_route_s1))
            event.connection.send(msg)

        if a and a.protodst == "10.0.0.6":
            msg = of.ofp_packet_out(data=event.ofp)
            msg.actions.append(of.ofp_action_output(port=default_route_s1))
            event.connection.send(msg)

        if a and a.protodst == "10.0.0.1":
            msg = of.ofp_packet_out(data=event.ofp)
            msg.actions.append(of.ofp_action_output(port=1))
            event.connection.send(msg)

        if a and a.protodst == "10.0.0.2":
            msg = of.ofp_packet_out(data=event.ofp)
            msg.actions.append(of.ofp_action_output(port=2))
            event.connection.send(msg)

        if a and a.protodst == "10.0.0.3":
            msg = of.ofp_packet_out(data=event.ofp)
            msg.actions.append(of.ofp_action_output(port=3))
            event.connection.send(msg)

        ip = packet.find('ipv4')
        if ip and ip.dstip == "10.0.0.1":
            msg = of.ofp_flow_mod()
            msg.priority = 100
            msg.idle_timeout = 0
            msg.hard_timeout = 0
            msg.match.dl_type = 0x0800  # rule for IP packets (x0800)
            msg.match.nw_dst = "10.0.0.1"
            msg.actions.append(of.ofp_action_output(port=1))
            event.connection.send(msg)

        if ip and ip.dstip == "10.0.0.2":
            msg = of.ofp_flow_mod()
            msg.priority = 100
            msg.idle_timeout = 0
            msg.hard_timeout = 0
            msg.match.dl_type = 0x0800
            msg.match.nw_dst = "10.0.0.2"
            msg.actions.append(of.ofp_action_output(port=2))
            event.connection.send(msg)

        if ip and ip.dstip == "10.0.0.3":
            msg = of.ofp_flow_mod()
            msg.priority = 100
            msg.idle_timeout = 0
            msg.hard_timeout = 0
            msg.match.dl_type = 0x0800
            msg.match.nw_dst = "10.0.0.3"
            msg.actions.append(of.ofp_action_output(port=3))
            event.connection.send(msg)

        if ip and (ip.dstip == "10.0.0.4" or ip.dstip == "10.0.0.5" or ip.dstip == "10.0.0.6"):
            global other_intents, current_flows, current_delays, current_routing

            src = None
            if ip.srcip == "10.0.0.1":
                src = 'h1'
            elif ip.srcip == "10.0.0.2":
                src = 'h2'
            elif ip.srcip == "10.0.0.3":
                src = 'h3'

            dst = None
            if ip.dstip == "10.0.0.4":
                dst = 'h4'
            elif ip.dstip == "10.0.0.5":
                dst = 'h5'
            elif ip.dstip == "10.0.0.6":
                dst = 'h6'

            unspecified_flow = {'source': src, 'destination': dst}
            other_intents.append(unspecified_flow)

            best_path_flows = None
            optimal_path = None
            for x, delay in enumerate(current_delays):
                if x == 0 or current_flows[delay['path']] <= best_path_flows:
                    best_path_flows = current_flows[delay['path']]
                    optimal_path = delay['path']
            current_flows[optimal_path] += 1
            current_routing.append({'intent': unspecified_flow, 'path': optimal_path})

            print "New routing path for unspecified flow: ", unspecified_flow
            print "New path: ", optimal_path
            print "\nCurrent flows: S2: ", current_flows['s2'], "; S3: ", current_flows['s3'], "; S4: ", current_flows['s4'], "\n"
            modify_flow(src, dst, optimal_path)

    elif event.connection.dpid == s2_dpid:
        msg = of.ofp_flow_mod()
        msg.priority = 10
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.in_port = 1
        msg.match.dl_type = 0x0806  # rule for ARP packets (x0806)
        msg.actions.append(of.ofp_action_output(port=2))
        event.connection.send(msg)

        msg = of.ofp_flow_mod()
        msg.priority = 10
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.in_port = 1
        msg.match.dl_type = 0x0800
        msg.actions.append(of.ofp_action_output(port=2))
        event.connection.send(msg)

        msg = of.ofp_flow_mod()
        msg.priority = 10
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.in_port = 2
        msg.match.dl_type = 0x0806
        msg.actions.append(of.ofp_action_output(port=1))
        event.connection.send(msg)

        msg = of.ofp_flow_mod()
        msg.priority = 10
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.in_port = 2
        msg.match.dl_type = 0x0800
        msg.actions.append(of.ofp_action_output(port=1))
        event.connection.send(msg)

    elif event.connection.dpid == s3_dpid:
        msg = of.ofp_flow_mod()
        msg.priority = 10
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.in_port = 1
        msg.match.dl_type = 0x0806
        msg.actions.append(of.ofp_action_output(port=2))
        event.connection.send(msg)

        msg = of.ofp_flow_mod()
        msg.priority = 10
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.in_port = 1
        msg.match.dl_type = 0x0800
        msg.actions.append(of.ofp_action_output(port=2))
        event.connection.send(msg)

        msg = of.ofp_flow_mod()
        msg.priority = 10
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.in_port = 2
        msg.match.dl_type = 0x0806
        msg.actions.append(of.ofp_action_output(port=1))
        event.connection.send(msg)

        msg = of.ofp_flow_mod()
        msg.priority = 10
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.in_port = 2
        msg.match.dl_type = 0x0800
        msg.actions.append(of.ofp_action_output(port=1))
        event.connection.send(msg)

    elif event.connection.dpid == s4_dpid:
        msg = of.ofp_flow_mod()
        msg.priority = 10
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.in_port = 1
        msg.match.dl_type = 0x0806
        msg.actions.append(of.ofp_action_output(port=2))
        event.connection.send(msg)

        msg = of.ofp_flow_mod()
        msg.priority = 10
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.in_port = 1
        msg.match.dl_type = 0x0800
        msg.actions.append(of.ofp_action_output(port=2))
        event.connection.send(msg)

        msg = of.ofp_flow_mod()
        msg.priority = 10
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.in_port = 2
        msg.match.dl_type = 0x0806
        msg.actions.append(of.ofp_action_output(port=1))
        event.connection.send(msg)

        msg = of.ofp_flow_mod()
        msg.priority = 10
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.in_port = 2
        msg.match.dl_type = 0x0800
        msg.actions.append(of.ofp_action_output(port=1))
        event.connection.send(msg)

    elif event.connection.dpid == s5_dpid:
        a = packet.find('arp')
        if a and a.protodst == "10.0.0.4":
            msg = of.ofp_packet_out(data=event.ofp)
            msg.actions.append(of.ofp_action_output(port=4))
            event.connection.send(msg)

        if a and a.protodst == "10.0.0.5":
            msg = of.ofp_packet_out(data=event.ofp)
            msg.actions.append(of.ofp_action_output(port=5))
            event.connection.send(msg)

        if a and a.protodst == "10.0.0.6":
            msg = of.ofp_packet_out(data=event.ofp)
            msg.actions.append(of.ofp_action_output(port=6))
            event.connection.send(msg)

        if a and a.protodst == "10.0.0.1":
            msg = of.ofp_packet_out(data=event.ofp)
            msg.actions.append(of.ofp_action_output(port=default_route_s5))
            event.connection.send(msg)

        if a and a.protodst == "10.0.0.2":
            msg = of.ofp_packet_out(data=event.ofp)
            msg.actions.append(of.ofp_action_output(port=default_route_s5))
            event.connection.send(msg)

        if a and a.protodst == "10.0.0.3":
            msg = of.ofp_packet_out(data=event.ofp)
            msg.actions.append(of.ofp_action_output(port=default_route_s5))
            event.connection.send(msg)

        msg = of.ofp_flow_mod()
        msg.priority = 100
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.dl_type = 0x0800
        msg.match.nw_dst = "10.0.0.4"
        msg.actions.append(of.ofp_action_output(port=4))
        event.connection.send(msg)

        msg = of.ofp_flow_mod()
        msg.priority = 100
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.dl_type = 0x0800
        msg.match.nw_dst = "10.0.0.5"
        msg.actions.append(of.ofp_action_output(port=5))
        event.connection.send(msg)

        msg = of.ofp_flow_mod()
        msg.priority = 100
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.match.dl_type = 0x0800
        msg.match.nw_dst = "10.0.0.6"
        msg.actions.append(of.ofp_action_output(port=6))
        event.connection.send(msg)


# As usually, launch() is the function called by POX to initialize the component (routing_controller.py in our case)
# indicated by a parameter provided to pox.py

def launch():
    global start_time
    start_time = time.time() * 1000 * 10  # factor *10 applied to increase the accuracy for short delays (capture tenths of ms)
    print "start_time:", start_time / 10

    # core is an instance of class POXCore (EventMixin) and it can register objects.
    # An object with name xxx can be registered to core instance which makes this object become a "component" available as pox.core.core.xxx.
    # for examples see e.g. https://noxrepo.github.io/pox-doc/html/#the-openflow-nexus-core-openflow
    core.openflow.addListenerByName("PortStatsReceived",
                                    _handle_portstats_received)  # listen for port stats , https://noxrepo.github.io/pox-doc/html/#statistics-events
    core.openflow.addListenerByName("ConnectionUp",
                                    _handle_ConnectionUp)  # listen for the establishment of a new control channel with a switch, https://noxrepo.github.io/pox-doc/html/#connectionup
    core.openflow.addListenerByName("PacketIn",
                                    _handle_PacketIn)  # listen for the reception of packet_in message from switch, https://noxrepo.github.io/pox-doc/html/#packetin
    # core.openflow.addListenerByName("FlowStatsReceived",
    #                                 _handle_flowstats_received)

