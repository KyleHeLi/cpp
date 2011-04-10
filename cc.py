#!/usr/bin/env python
'''
Connectivity Checker

A simple tool to evaluate the connectivity of a graph, given a failure rate.

Intended to help answer questions about the fault tolerance aspects of SDN,
and the algorithms for bootstrapping the switch-controller connection. 
'''
import networkx as nx
import logging


lg = logging.getLogger("cc")

def compute(g, link_fail_prob, node_fail_prob, max_failures, alg):
    '''Compute connectivity assuming independent failures.

    @param g: input graph as NetworkX Graph
    @param link_fail_prob: link failure probability
    @param node_fail_prob: node failure probability
    @param max_failures: max failures to consider
    @param alg: static controller connection algorithm, one of:
        stp: random dumb spanning tree rooting at controller
        sssp: Dijksta's, produces shortest-path tree to controller
        edge-2: Edge disjoint shortest pair:
            http://en.wikipedia.org/wiki/Edge_disjoint_shortest_pair_algorithm
        edge-disjoint-n
        node-disjoint-n
        best-available: use the best
        any: any connectivity, no matter how bad (ignore latency)

    @return conn: distribution of switch-to-controller connectivity
    '''

    # Consider one failure only, for now.  Eventually extend to handle
    # multiple failures by pushing all combinations as lists onto a stack
    # and considering the effect of each one.
    if max_failures != 1:
        raise Exception("only 1 failure supported")

    if alg != 'sssp':
        raise Exception("only sssp (Dijkstra's) supported")

    if node_fail_prob != 0:
        raise Exception("only link failures supported")

    if link_fail_prob * g.number_of_nodes() > 1.0:
        raise Exception("unable to handle case where > 1 failure is typical")

    # Store pairs of (probability, uptime) to be used to build an
    # uptime distribution later
    connectivities = []

    # For each controller location (assume directly attached to a switch
    # with a perfectly reliable link), repeat the analysis.
    for controller_node in g.nodes():

        lg.debug("   >>> considering controller at: %s" % controller_node)

        # Store pairs of (probability, connectivity)
        uptime_dist = []

        # Compute SSSP.
        # Need a list of nodes from each switch to the controller to see how
        # connectivity changes when links go down.
        paths = nx.single_source_shortest_path(g, controller_node)
        # Store the flattened set of shortest paths to the controller as a
        # graph.  Useful later to only consider those nodes or edges that might
        # have an effect on reliability.
        used = nx.Graph()
        lg.debug("paths: %s" % paths)
        for path in paths.values():
            lg.debug("flattening path: %s" % path)
            used.add_path(path)
        lg.debug(used.edges())

        for failed_edge in g.edges():
            lg.debug("------------------------")
            lg.debug("considering failed edge: %s" % str(failed_edge))

            # If failed edge is not a part of the path set, then no effect on
            # reliability.
            if used.has_edge(failed_edge[0], failed_edge[1]):
                # Failed edge matters for connectivity for some switch.

                # Check switch-to-controller connectivity.
                connected = 0
                disconnected = 0
                for sw in g.nodes():
                    path_graph = nx.Graph()
                    path_graph.add_path(paths[sw])
                    #lg.debug("path graph edges: %s" % path_graph.edges())
                    if path_graph.has_edge(failed_edge[0], failed_edge[1]):
                        lg.debug("disconnected sw: %s" % sw)
                        disconnected += 1
                    else:
                        lg.debug("connected sw: %s" % sw)
                        connected += 1
                connectivity = float(connected) / g.number_of_nodes()
                uptime_dist.append((link_fail_prob, connectivity))
            else:
                # No effect on connectivity.
                lg.debug("edge not in sssp graph; ignoring")
                uptime_dist.append((link_fail_prob, 1.0))

        lg.debug("uptime dist: %s" % uptime_dist)
        fraction_covered = sum([x[0] for x in uptime_dist])
        lg.debug("covered %s%% of the uptime distribution" % fraction_covered)
        weighted_conn = 0
        for percentage, conn in uptime_dist:
            weighted_conn += percentage * conn
        # Account for time when nothing's broken:
        weighted_conn += (1.0 - fraction_covered) * 1.0
        lg.debug("weighted connectivity: %s" % weighted_conn)

        connectivities.append(weighted_conn)

    avg_conn = sum(connectivities) / len(connectivities)
    print "average connectivity: %f" % avg_conn

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    g = nx.complete_graph(3)
    print compute(g, 0.1, 0, 1, 'sssp')
