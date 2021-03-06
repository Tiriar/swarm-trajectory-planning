import math
import time
import utils as ut
import vrep

__author__ = 'BRICH'


def start(clientID, quads, targets, speed, proxs, path, leadfoll=False):
    """
    Boids model program for experimental graph edges evaluation
    :param clientID: ID of the VRep connection
    :param quads: quadrotor handles
    :param targets: quadrotor target handles
    :param speed: speed of quadrotors
    :param proxs: proximity sensor handles
    :param path: quadrotor path coordinates
    :param leadfoll: True - leader/followers mode, False - all boids following path (default)
    """

    # definition of constants
    quadsNum = len(quads)   # number of quadrotors
    viewRange = 3       # view range of quadrotors
    smp = 0.2           # sampling period
    kS = [0.30, 2.0]    # separation constants [multiplication const, power const]
    kC = [0.30, 0.0]    # cohesion constants [multiplication const, power const]
    kA = [0.00, 0.0]    # alignment constants [multiplication const, power const]
    kD = [speed, 1.0]   # path following constants [multiplication const, power const]
    kO = [0.20, 2.0]    # obstacle avoidance constants [multiplication const, power const]

    # data stream init
    for i in range(quadsNum):
        vrep.simxGetObjectPosition(clientID, quads[i], -1, vrep.simx_opmode_streaming)
        vrep.simxGetObjectVelocity(clientID, quads[i], vrep.simx_opmode_streaming)
        vrep.simxReadProximitySensor(clientID, proxs[i], vrep.simx_opmode_streaming)

    # variables init
    position = [[0 for _ in range(3)] for _ in range(quadsNum)]     # position of quadrotors
    velocity = [[0 for _ in range(3)] for _ in range(quadsNum)]     # velocity of quadrotors
    closest = [[0 for _ in range(3)] for _ in range(quadsNum)]      # coords of closest obstacle to quads
    visibleQuads = [[0 for _ in range(quadsNum)] for _ in range(quadsNum)]  # visible quadrotors
    individualTarget = [0]*quadsNum     # current waypoint index for each quadrotor

    # get closest boid to starting point
    leader = 0
    _, tmp = vrep.simxGetObjectPosition(clientID, quads[0], -1, vrep.simx_opmode_buffer)
    dist = ut.norm(ut.sub(path[1], tmp))
    for i in range(1, quadsNum):
        _, tmp = vrep.simxGetObjectPosition(clientID, quads[i], -1, vrep.simx_opmode_buffer)
        nrm = ut.norm(ut.sub(path[1], tmp))
        if nrm < dist:
            dist = nrm
            leader = i

    # main boids program
    print('Evaluating '+str(len(path))+' edges:')
    number = 0
    cnt = [0]*quadsNum
    finished = [0]*len(path)
    last = [False]*quadsNum
    end = False
    t1 = vrep.simxGetLastCmdTime(clientID)
    ec = []
    while vrep.simxGetConnectionId(clientID) != -1:
        time.sleep(smp)

        separation = [[0 for _ in range(3)] for _ in range(quadsNum)]   # separation force
        cohesion = [[0 for _ in range(3)] for _ in range(quadsNum)]     # cohesion force
        alignment = [[0 for _ in range(3)] for _ in range(quadsNum)]    # alignment force
        destination = [[0 for _ in range(3)] for _ in range(quadsNum)]  # path following force
        avoidance = [[0 for _ in range(3)] for _ in range(quadsNum)]    # obstacle avoidance force
        output = [[0 for _ in range(3)] for _ in range(quadsNum)]       # output force

        # read data from VRep
        for i in range(quadsNum):
            _, position[i] = vrep.simxGetObjectPosition(clientID, quads[i], -1, vrep.simx_opmode_buffer)
            _, velocity[i], _ = vrep.simxGetObjectVelocity(clientID, quads[i], vrep.simx_opmode_buffer)
            _, res, closest[i], _, _ = vrep.simxReadProximitySensor(clientID, proxs[i], vrep.simx_opmode_buffer)
            if not res:
                closest[i] = [0, 0, 0]
            closest[i][2] = 0

        # compute visible quadrotors
        for i in range(quadsNum):
            for j in range(quadsNum):
                if i != j:
                    temp = ut.sub(position[i], position[j])
                    if ut.norm(temp) < viewRange:
                        visibleQuads[i][j] = 1
                    else:
                        visibleQuads[i][j] = 0

        for i in range(quadsNum):
            # compute separation force
            for j in range(quadsNum):
                if i != j and visibleQuads[i][j] == 1:
                    temp = ut.sub(position[i], position[j])
                    nrm = ut.norm(temp)
                    if nrm != 0:
                        temp = ut.mul(temp, kS[0]/(nrm**kS[1]))
                        separation[i] = ut.add(separation[i], temp)

            # compute cohesion and alignment forces
            center = [0, 0, 0]  # center of the swarm
            if sum(visibleQuads[i]) != 0:
                for j in range(quadsNum):
                    if i != j and visibleQuads[i][j] == 1:
                        temp = ut.mul(position[j], 1/sum(visibleQuads[i]))
                        center = ut.add(center, temp)
                        temp = ut.mul(velocity[j], 1/sum(visibleQuads[i]))
                        alignment[i] = ut.add(alignment[i], temp)
                cohesion[i] = ut.sub(center, position[i])
            nrm = ut.norm(cohesion[i])
            if nrm != 0:
                cohesion[i] = ut.mul(cohesion[i], kC[0]/(nrm**kC[1]))
            nrm = ut.norm(alignment[i])
            if nrm != 0:
                alignment[i] = ut.mul(alignment[i], kA[0]/(nrm**kA[1]))

            # compute path following force
            check = False
            if not leadfoll or i == leader or end:
                nrm = ut.norm(ut.sub(position[i][0:2], path[individualTarget[i]][0:2]))
                if end:
                    if finished[i] == 0 and nrm < 2:
                        finished[i] += 1
                    if sum(finished) == quadsNum:
                        return ec
                else:
                    if individualTarget[i] != 0:
                        if not last[i]:
                            tmp = min(individualTarget)
                            if individualTarget[i] == tmp and tmp != max(individualTarget):
                                cnt[i] += 1
                            vec1 = ut.sub(path[individualTarget[i]-1], path[individualTarget[i]])
                            vec2 = ut.sub(position[i], path[individualTarget[i]])
                            if nrm <= 1 or cnt[i] > 30 or ut.angle(vec1, vec2) >= math.pi/2:
                                if cnt[i] != 0:
                                    cnt = [0]*quadsNum
                                finished[individualTarget[i]] += 1
                                if leadfoll or finished[individualTarget[i]] == quadsNum:
                                    check = True
                                if individualTarget[i] < len(path)-1:
                                    individualTarget[i] += 1
                                else:
                                    last[i] = True
                    else:
                        vec1 = ut.sub(path[individualTarget[i]+1], path[individualTarget[i]])
                        vec2 = ut.sub(position[i], path[individualTarget[i]])
                        if nrm <= 1 or ut.angle(vec1, vec2) <= math.pi/2:
                            finished[individualTarget[i]] += 1
                            if leadfoll or finished[individualTarget[i]] == quadsNum:
                                check = True
                            individualTarget[i] += 1
                    if check:
                        t2 = vrep.simxGetLastCmdTime(clientID)
                        ec.append((t2-t1)/1000)
                        print('Edge #'+str(number)+': '+str((t2-t1)/1000)+'s')
                        number += 1
                        if number == len(path):
                            return ec
                        t1 = t2
                        if (leadfoll and finished[-1] == 1) or finished[-1] == quadsNum:
                            end = True
                            individualTarget = [0]*quadsNum
                            finished = [0]*quadsNum
                destination[i] = ut.sub(path[individualTarget[i]], position[i])
                nrm = ut.norm(destination[i])
                if nrm != 0:
                    destination[i] = ut.mul(destination[i], kD[0]/(nrm**kD[1]))

            # compute output force without obstacle avoidance
            output[i] = separation[i]
            output[i] = ut.add(output[i], cohesion[i])
            output[i] = ut.add(output[i], alignment[i])
            output[i] = ut.add(output[i], destination[i])

            # compute obstacle avoidance force
            # angle = ut.angle(closest[i], output[i])
            # if angle > math.pi/2+0.3:
            #     avoidance[i] = [0, 0, 0]
            # else:
            avoidance[i] = ut.sub([0, 0, 0], closest[i])
            nrm = ut.norm(avoidance[i])
            if nrm != 0:
                avoidance[i] = ut.mul(avoidance[i], kO[0]/(nrm**kO[1]))

            # compute output force
            output[i] = ut.add(output[i], avoidance[i])
            if position[i][2] < 0.5:
                output[i][2] = 0.05

        # export output to VRep
        for i in range(quadsNum):
            vrep.simxSetObjectPosition(clientID, targets[i], quads[i], output[i], vrep.simx_opmode_streaming)
