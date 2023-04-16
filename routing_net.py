from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import RemoteController
import time
import thread


# testing delays
def change_delays():
    global s1, s2, s3, s4

    interval_time = 10
    test_delays = []
    test_delays.append(['200ms', '50ms', '10ms'])
    test_delays.append(['50ms', '40ms', '60ms'])
    test_delays.append(['400ms', '5ms', '100ms'])
    test_delays.append(['2ms', '500ms', '40ms'])

    for delays in test_delays:
        s1.cmdPrint('tc qdisc del dev s1-eth4 root')
        s1.cmdPrint('tc qdisc add dev s1-eth4 root handle 10: netem delay {}'.format(delays[0]))
        s2.cmdPrint('tc qdisc del dev s2-eth1 root')
        s2.cmdPrint('tc qdisc add dev s2-eth1 root handle 10: netem delay {}'.format(delays[0]))

        s1.cmdPrint('tc qdisc del dev s1-eth5 root')
        s1.cmdPrint('tc qdisc add dev s1-eth5 root handle 10: netem delay {}'.format(delays[1]))
        s3.cmdPrint('tc qdisc del dev s3-eth1 root')
        s3.cmdPrint('tc qdisc add dev s3-eth1 root handle 10: netem delay {}'.format(delays[1]))

        s1.cmdPrint('tc qdisc del dev s1-eth6 root')
        s1.cmdPrint('tc qdisc add dev s1-eth6 root handle 10: netem delay {}'.format(delays[2]))
        s4.cmdPrint('tc qdisc del dev s4-eth1 root')
        s4.cmdPrint('tc qdisc add dev s4-eth1 root handle 10: netem delay {}'.format(delays[2]))

        time.sleep(interval_time)


def runNetwork():
    global s1, s2, s3, s4, h1, h2, h3
    # mininet topology initialization

    my_controller = RemoteController('c0', ip='127.0.0.1', port=6633)
    net = Mininet(host=CPULimitedHost, link=TCLink, autoSetMacs=True)

    # create topology
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    s3 = net.addSwitch('s3')
    s4 = net.addSwitch('s4')
    s5 = net.addSwitch('s5')
    h1 = net.addHost('h1')
    h2 = net.addHost('h2')
    h3 = net.addHost('h3')
    h4 = net.addHost('h4')
    h5 = net.addHost('h5')
    h6 = net.addHost('h6')

    # , use_htb=True
    h1s1 = net.addLink(h1, s1, bw=10, delay='0ms', loss=0, max_queue_size=10000, use_htb=True)
    h2s1 = net.addLink(h2, s1, bw=10, delay='0ms', loss=0, max_queue_size=10000, use_htb=True)
    h3s1 = net.addLink(h3, s1, bw=10, delay='0ms', loss=0, max_queue_size=10000, use_htb=True)
    s1s2 = net.addLink(s1, s2, bw=10, delay='200ms', loss=0, max_queue_size=1000, use_htb=True)
    s1s3 = net.addLink(s1, s3, bw=10, delay='50ms', loss=0, max_queue_size=1000, use_htb=True)
    s1s4 = net.addLink(s1, s4, bw=10, delay='10ms', loss=0, max_queue_size=1000, use_htb=True)
    s2s5 = net.addLink(s2, s5, bw=10, delay='0ms', loss=0, max_queue_size=10000, use_htb=True)
    s3s5 = net.addLink(s3, s5, bw=10, delay='0ms', loss=0, max_queue_size=10000, use_htb=True)
    s4s5 = net.addLink(s4, s5, bw=10, delay='0ms', loss=0, max_queue_size=10000, use_htb=True)
    s5h4 = net.addLink(s5, h4, bw=10, delay='0ms', loss=0, max_queue_size=10000, use_htb=True)
    s5h5 = net.addLink(s5, h5, bw=10, delay='0ms', loss=0, max_queue_size=10000, use_htb=True)
    s5h6 = net.addLink(s5, h6, bw=10, delay='0ms', loss=0, max_queue_size=10000, use_htb=True)

    net.addController(my_controller)

    net.start()

    # Dumping host connections
    dumpNodeConnections(net.hosts)

    thread.start_new_thread(change_delays, ())

    CLI(net)  # launch simple Mininet CLI terminal window
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    runNetwork()
