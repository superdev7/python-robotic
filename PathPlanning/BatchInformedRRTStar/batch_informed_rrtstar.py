"""
Batch Informed Trees based path planning

author: Karan Chawla(@karanchawla)

Reference: https://arxiv.org/abs/1405.5848
"""

import random
import numpy as np
import copy
import operator
import math
import matplotlib.pyplot as plt

show_animation = True


class RTree(object):

    def __init__(self, start=[0,0], lowerLimit=[0,0], upperLimit=[10,10], resolution=1):
        self.vertices = dict()
        
        self.edges = []
        self.start = start
        self.lowerLimit = lowerLimit
        self.upperLimit = upperLimit
        self.dimension = len(lowerLimit)
        self.num_cells = [0] * self.dimension
        self.resolution = resolution
        # compute the number of grid cells based on the limits and
        # resolution given
        for idx in range(self.dimension):
            self.num_cells[idx] = np.ceil(
                (upperLimit[idx] - lowerLimit[idx]) / resolution)

        vertex_id = self.realWorldToNodeId(start)
        self.vertices[vertex_id] = []

    def getRootId(self):
        # return the id of the root of the tree
        return 0

    def addVertex(self, vertex):
        # add a vertex to the tree
        vertex_id = self.realWorldToNodeId(vertex)
        self.vertices[vertex_id] = []
        return vertex_id

    def addEdge(self, v, x):
        # create an edge between v and x vertices
        if (v, x) not in self.edges:
            self.edges.append((v, x))
        # since the tree is undirected
        self.vertices[v].append(x)
        self.vertices[x].append(v)

    def realCoordsToGridCoord(self, real_coord):
        # convert real world coordinates to grid space
        # depends on the resolution of the grid
        # the output is the same as real world coords if the resolution
        # is set to 1
        coord = [0] * self.dimension
        for i in range(0, len(coord)):
            start = self.lowerLimit[i]  # start of the grid space
            coord[i] = np.around((real_coord[i] - start) / self.resolution)
        return coord

    def gridCoordinateToNodeId(self, coord):
        # This function maps a grid coordinate to a unique
        # node id
        nodeId = 0
        for i in range(len(coord) - 1, -1, -1):
            product = 1
            for j in range(0, i):
                product = product * self.num_cells[j]
            nodeId = nodeId + coord[i] * product
        return nodeId

    def realWorldToNodeId(self, real_coord):
        # first convert the given coordinates to grid space and then
        # convert the grid space coordinates to a unique node id
        return self.gridCoordinateToNodeId(self.realCoordsToGridCoord(real_coord))

    def gridCoordToRealWorldCoord(self, coord):
        # This function smaps a grid coordinate in discrete space
        # to a configuration in the full configuration space
        config = [0] * self.dimension
        for i in range(0, len(coord)):
            # start of the real world / configuration space
            start = self.lowerLimit[i]
            # step from the coordinate in the grid
            grid_step = self.resolution * coord[i]
            half_step = self.resolution / 2  # To get to middle of the grid
            config[i] = start + grid_step  # + half_step
        return config

    def nodeIdToGridCoord(self, node_id):
        # This function maps a node id to the associated
        # grid coordinate
        coord = [0] * len(self.lowerLimit)
        for i in range(len(coord) - 1, -1, -1):
            # Get the product of the grid space maximums
            prod = 1
            for j in range(0, i):
                prod = prod * self.num_cells[j]
            coord[i] = np.floor(node_id / prod)
            node_id = node_id - (coord[i] * prod)
        return coord

    def nodeIdToRealWorldCoord(self, nid):
        # This function maps a node in discrete space to a configuraiton
        # in the full configuration space
        return self.gridCoordToRealWorldCoord(self.nodeIdToGridCoord(nid))


class Node():

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.cost = 0.0
        self.parent = None


class BITStar(object):

    def __init__(self, start, goal,
                 obstacleList, randArea, eta=2.0,
                 expandDis=0.5, goalSampleRate=10, maxIter=200):
        self.start = start
        self.goal = goal

        self.minrand = randArea[0]
        self.maxrand = randArea[1]
        self.expandDis = expandDis
        self.goalSampleRate = goalSampleRate
        self.maxIter = maxIter
        self.obstacleList = obstacleList

        self.vertex_queue = []
        self.edge_queue = []
        self.samples = dict()
        self.g_scores = dict()
        self.f_scores = dict()
        self.nodes = dict()
        self.r = float('inf')
        self.eta = eta  # tunable parameter
        self.unit_ball_measure = 1
        self.old_vertices = []

        # initialize tree
        lowerLimit = [randArea[0], randArea[0]]
        upperLimit = [randArea[1], randArea[1]]
        self.tree = RTree(start=start,lowerLimit=lowerLimit,upperLimit=upperLimit,resolution=0.1)

    def plan(self, animation=True):

        self.startId = self.tree.realWorldToNodeId(self.start)
        self.goalId = self.tree.realWorldToNodeId(self.goal)

        # add goal to the samples
        self.samples[self.goalId] = self.goal
        self.g_scores[self.goalId] = float('inf')
        self.f_scores[self.goalId] = 0

        # add the start id to the tree
        self.tree.addVertex(self.start)
        self.g_scores[self.startId] = 0
        self.f_scores[self.startId] = self.computeHeuristicCost(
            self.startId, self.goalId)

        iterations = 0
        # max length we expect to find in our 'informed' sample space, starts as infinite
        cBest = self.g_scores[self.goalId]
        pathLen = float('inf')
        solutionSet = set()
        path = None

        # Computing the sampling space
        cMin = math.sqrt(pow(self.start[0] - self.goal[1], 2) +
                         pow(self.start[0] - self.goal[1], 2))
        xCenter = np.matrix([[(self.start[0] + self.goal[0]) / 2.0],
                             [(self.goal[1] - self.start[1]) / 2.0], [0]])
        a1 = np.matrix([[(self.goal[0]- self.start[0]) / cMin],
                        [(self.goal[1] - self.start[1]) / cMin], [0]])
        etheta = math.atan2(a1[1], a1[0])
        # first column of idenity matrix transposed
        id1_t = np.matrix([1.0, 0.0, 0.0])
        M = np.dot(a1, id1_t)
        U, S, Vh = np.linalg.svd(M, 1, 1)
        C = np.dot(np.dot(U, np.diag(
            [1.0, 1.0, np.linalg.det(U) * np.linalg.det(np.transpose(Vh))])), Vh)

        foundGoal = False
        # run until done
        while (iterations < self.maxIter):
            if len(self.vertex_queue) == 0 and len(self.edge_queue) == 0:
                # Using informed rrt star way of computing the samples
                self.samples.update(self.informedSample(
                    200, cBest, cMin, xCenter, C))
                # prune the tree
                self.r = 2.0
                if iterations != 0:
                    self.samples.update(self.informedSample(
                        200, cBest, cMin, xCenter, C))

                # make the old vertices the new vertices
                self.old_vertices += self.tree.vertices.keys()
                # add the vertices to the vertex queue
                for nid in self.tree.vertices.keys():
                    if nid not in self.vertex_queue:
                        self.vertex_queue.append(nid)
            # expand the best vertices until an edge is better than the vertex
            # this is done because the vertex cost represents the lower bound
            # on the edge cost
            while(self.bestVertexQueueValue() <= self.bestEdgeQueueValue()):
                self.expandVertex(self.bestInVertexQueue())

            # add the best edge to the tree
            bestEdge = self.bestInEdgeQueue()
            self.edge_queue.remove(bestEdge)

            # Check if this can improve the current solution
            estimatedCostOfVertex = self.g_scores[bestEdge[0]] + self.computeDistanceCost(
                bestEdge[0], bestEdge[1]) + self.computeHeuristicCost(bestEdge[1], self.goalId)
            estimatedCostOfEdge = self.computeDistanceCost(self.startId, bestEdge[0]) + self.computeHeuristicCost(
                bestEdge[0], bestEdge[1]) + self.computeHeuristicCost(bestEdge[1], self.goalId)
            actualCostOfEdge = self.g_scores[bestEdge[0]] + + \
                self.computeDistanceCost(bestEdge[0], bestEdge[1])

            if(estimatedCostOfVertex < self.g_scores[self.goalId]):
                if(estimatedCostOfEdge < self.g_scores[self.goalId]):
                    if(actualCostOfEdge < self.g_scores[self.goalId]):
                        # connect this edge
                        firstCoord = self.tree.nodeIdToRealWorldCoord(
                            bestEdge[0])
                        secondCoord = self.tree.nodeIdToRealWorldCoord(
                            bestEdge[1])
                        path = self.connect(firstCoord, secondCoord)
                        if path == None or len(path) == 0:
                            continue
                        nextCoord = path[len(path) - 1, :]
                        nextCoordPathId = self.tree.realWorldToNodeId(
                            nextCoord)
                        bestEdge = (bestEdge[0], nextCoordPathId)
                        try:
                            del self.samples[bestEdge[1]]
                        except(KeyError):
                            pass
                        eid = self.tree.addVertex(nextCoordPathId)
                        self.vertex_queue.append(eid)
                        if eid == self.goalId or bestEdge[0] == self.goalId or bestEdge[1] == self.goalId:
                            print("Goal found")
                            foundGoal = True

                        self.tree.addEdge(bestEdge[0], bestEdge[1])

                        g_score = self.computeDistanceCost(
                            bestEdge[0], bestEdge[1])
                        self.g_scores[bestEdge[1]] = g_score + \
                            self.g_scores[best_edge[0]]
                        self.f_scores[bestEdge[1]] = g_score + \
                            self.computeHeuristicCost(bestEdge[1], self.goalId)
                        self.updateGraph()

                        # visualize new edge
                        # if animation:
                        # 	self.drawGraph(xCenter=xCenter, cBest=cBest,
                        # 	   cMin=cMin, etheta=etheta, samples=samples)

                        for edge in self.edge_queue:
                            if(edge[0] == bestEdge[1]):
                                if self.g_scores[edge[0]] + self.computeDistanceCost(edge[0], bestEdge[1]) >= self.g_scores[self.goalId]:
                                    if(edge[0], best_edge[1]) in self.edge_queue:
                                        self.edge_queue.remove(
                                            (edge[0], bestEdge[1]))
                            if(edge[1] == bestEdge[1]):
                                if self.g_scores[edge[1]] + self.computeDistanceCost(edge[1], bestEdge[1]) >= self.g_scores[self.goalId]:
                                    if(edge[1], best_edge[1]) in self.edge_queue:
                                        self.edge_queue.remove(
                                            (edge[1], bestEdge[1]))
            else:
                self.edge_queue = []
                self.vertex_queue = []
            iterations += 1

        plan.append(self.goal)
        currId = self.goalId
        while (currId != self.startId):
            plan.append(seld.tree.nodeIdToRealWorldCoord(currId))
            currId = self.nodes[currId]

        plan.append(self.startId)
        plan = plan[::-1]  # reverse the plan
        return np.array(plan)

    # def expandVertex(self, vertex):

    # def prune(self, c):

    def computeHeuristicCost(self, start_id, goal_id):
        # Using Manhattan distance as heuristic
        start = np.array(self.tree.nodeIdToRealWorldCoord(start_id))
        goal = np.array(self.tree.nodeIdToRealWorldCoord(goal_id))

        return np.linalg.norm(start - goal, 2)

    def computeDistanceCost(self, vid, xid):
        # L2 norm distance
        start = np.array(self.tree.nodeIdToRealWorldCoord(vid))
        stop = np.array(self.tree.nodeIdToRealWorldCoord(xid))

        return np.linalg.norm(stop - start, 2)

    def radius(self, q):
        dim = len(start)  # dimensions
        space_measure = self.minrand * self.maxrand  # volume of the space

        min_radius = self.eta * 2.0 * pow((1.0 + 1.0 / dim) *
                                          (space_measure / self.unit_ball_measure), 1.0 / dim)
        return min_radius * pow(numpy.log(q) / q, 1 / dim)

    # Return the closest sample
    # def getNearestSample(self):

    # Sample free space confined in the radius of ball R
    def informedSample(self, m, cMax, cMin, xCenter, C):
        samples = dict()
        for i in range(m + 1):
            if cMax < float('inf'):
                r = [cMax / 2.0,
                     math.sqrt(cMax**2 - cMin**2) / 2.0,
                     math.sqrt(cMax**2 - cMin**2) / 2.0]
                L = np.diag(r)
                xBall = self.sampleUnitBall()
                rnd = np.dot(np.dot(C, L), xBall) + xCenter
                rnd = [rnd[(0, 0)], rnd[(1, 0)]]
                random_id = self.tree.realWorldToNodeId(rnd)
                samples[random_id] = rnd
            else:
                rnd = self.sampleFreeSpace()
                random_id = self.tree.realWorldToNodeId(rnd)
                samples[random_id] = rnd
        return samples

    # Sample point in a unit ball
    def sampleUnitBall(self):
        a = random.random()
        b = random.random()

        if b < a:
            a, b = b, a

        sample = (b * math.cos(2 * math.pi * a / b),
                  b * math.sin(2 * math.pi * a / b))
        return np.array([[sample[0]], [sample[1]], [0]])

    def sampleFreeSpace(self):
        rnd = [random.uniform(self.minrand, self.maxrand),
               random.uniform(self.minrand, self.maxrand)]

        return rnd

    def bestVertexQueueValue(self):
        if(len(self.vertex_queue) == 0):
            return float('inf')
        values = [self.g_scores[v] +
                  self.computeHeuristicCost(v, self.goalId) for v in self.vertex_queue]
        values.sort()
        return values[0]

    def bestEdgeQueueValue(self):
        if(len(self.edge_queue) == 0):
            return float('inf')
        # return the best value in the queue by score g_tau[v] + c(v,x) + h(x)
        values = [self.g_scores[e[0]] + self.computeDistanceCost(e[0], e[1]) +
                  self.computeHeuristicCost(e[1], self.goalId) for e in self.edge_queue]
        values.sort(reverse=True)
        return values[0]

    def bestInVertexQueue(self):
        # return the best value in the vertex queue
        v_plus_vals = [(v, self.g_scores[v] + self.computeHeuristicCost(v, self.goalId))
                       for v in self.vertex_queue]
        v_plus_vals = sorted(v_plus_vals, key=lambda x: x[1])

        return v_plus_vals[0][0]

    def bestInEdgeQueue(self):
        e_and_values = [(e[0], e[1], self.g_scores[e[0]] + self.computeDistanceCost(
            e[0], e[1]) + self.computeHeuristicCost(e[1], self.goalId)) for e in self.edge_queue]
        e_and_values = sorted(e_and_values, key=lambda x: x[2])

        return (e_and_values[0][0], e_and_values[0][1])

    def expandVertex(self, vid):
        self.vertex_queue.remove(vid)

        # get the coordinates for given vid
        currCoord = np.array(self.tree.nodeIdToRealWorldCoord(vid))

        # get the nearest value in vertex for every one in samples where difference is
        # less than the radius
        neigbors = []
        for sid, scoord in self.samples.items():
            scoord = np.array(scoord)
            if(np.linalg.norm(scoord - currCoord, 2) <= self.r and sid != vid):
                neigbors.append((sid, scoord))

        # add the vertex to the edge queue
        if vid not in self.old_vertices:
            neigbors = []
            for v, edges in self.tree.vertices.items():
                if v != vid and (v, vid) not in self.edge_queue:
                    vcoord = self.tree.nodeIdToRealWorldCoord(v)
                    if(np.linalg.norm(vcoord - currCoord, 2) <= self.r):
                        neigbors.append((vid, vcoord))

        # add an edge to the edge queue is the path might improve the solution
        for neighbor in neigbors:
            sid = neighbor[0]
            estimated_f_score = self.computeDistanceCost(
                self.startId, vid) + self.computeHeuristicCost(sid, self.goalId) + self.computeDistanceCost(vid, sid)
            if estimated_f_score < self.g_scores[self.goalId]:
                self.edge_queue.append((vid, sid))

    def updateGraph(self):
        closedSet = []
        openSet = []
        currId = self.startId
        openSet.append(currId)

        # do some plotting

        foundGoal = False

        while len(openSet) != 0:
            # get the element with lowest f_score
            minn = float('inf')
            min_node = None
            min_idx = 0
            for i in range(0, len(openSet)):
                try:
                    f_score = self.f_scores[openSet[i]]
                except:
                    pass
                if f_score < minn:
                    minn = f_score
                    min_node = openSet[i]
                    min_idx = i
            currId = min_node

            openSet.pop(min_idx)

            # Check if we're at the goal
            if(currId == self.goalId):
                foundGoal = True
                break

            if(currId not in closedSet):
                closedSet.append(currId)

            # find a non visited successor to the current node
            successors = self.tree.vertices[currId]
            for succesor in successors:
                if(succesor in closedSet):
                    continue
                else:
                    # claculate tentative g score
                    succesorCoord = self.tree.nodeIdToRealWorldCoord(succesor)
                    g_score = self.g_scores[currId] + \
                        self.computeDistanceCost(currId, succesor)
                    if succesor not in openSet:
                        # add the successor to open set
                        openSet.append(succesor)
                    elif g_score >= self.g_scores[succesor]:
                        continue

                    # update g and f scores
                    self.g_scores[succesor] = g_score
                    self.f_scores[succesor] = f_score + \
                        self.computeHeuristicCost(succesor, self.goalId)

                    # store the parent and child
                    self.nodes[succesor] = currId

    def drawGraph(self, xCenter=None, cBest=None, cMin=None, etheta=None, samples=None):
        print("Plotting Graph")
        plt.clf()
        for rnd in samples:
            if rnd is not None:
                plt.plot(rnd[0], rnd[1], "^k")
                if cBest != float('inf'):
                    self.plot_ellipse(xCenter, cBest, cMin, etheta)

        # for node in self.nodeList:
        # 	if node.parent is not None:
        # 		if node.x or node.y is not None:
        # 			plt.plot([node.x, self.nodeList[node.parent].x], [
        # 					node.y, self.nodeList[node.parent].y], "-g")

        for (ox, oy, size) in self.obstacleList:
            plt.plot(ox, oy, "ok", ms=30 * size)

        plt.plot(self.start.x, self.start.y, "xr")
        plt.plot(self.goal.x, self.goal.y, "xr")
        plt.axis([-2, 15, -2, 15])
        plt.grid(True)
        plt.pause(5)

    def plot_ellipse(self, xCenter, cBest, cMin, etheta):

        a = math.sqrt(cBest**2 - cMin**2) / 2.0
        b = cBest / 2.0
        angle = math.pi / 2.0 - etheta
        cx = xCenter[0]
        cy = xCenter[1]

        t = np.arange(0, 2 * math.pi + 0.1, 0.1)
        x = [a * math.cos(it) for it in t]
        y = [b * math.sin(it) for it in t]
        R = np.matrix([[math.cos(angle), math.sin(angle)],
                       [-math.sin(angle), math.cos(angle)]])
        fx = R * np.matrix([x, y])
        px = np.array(fx[0, :] + cx).flatten()
        py = np.array(fx[1, :] + cy).flatten()
        plt.plot(cx, cy, "xc")
        plt.plot(px, py, "--c")


def main():
    print("Starting Batch Informed Trees Star planning")
    obstacleList = [
        (5, 5, 0.5),
        (9, 6, 1),
        (7, 5, 1),
        (1, 5, 1),
        (3, 6, 1),
        (7, 9, 1)
    ]

    bitStar = BITStar(start=[0, 0], goal=[5, 10], obstacleList=obstacleList,
                      randArea=[0, 15])
    path = bitStar.plan(animation=show_animation)
    print("Done")


if __name__ == '__main__':
    main()
