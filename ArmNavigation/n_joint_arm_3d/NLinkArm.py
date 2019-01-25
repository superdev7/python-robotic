import numpy as np
import math
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt

class Link:
    def __init__(self, dh_params):
        self.dh_params_ = dh_params

    def transformation_matrix(self):
        theta = self.dh_params_[0]
        alpha = self.dh_params_[1]
        a = self.dh_params_[2]
        d = self.dh_params_[3]

        trans = np.array(
            [[math.cos(theta), -math.sin(theta), 0, a],
             [math.cos(alpha) * math.sin(theta), math.cos(alpha) * math.cos(theta), -math.sin(alpha), -d * math.sin(alpha)],
             [math.sin(alpha) * math.sin(theta), math.sin(alpha) * math.cos(theta), math.cos(alpha), d * math.cos(alpha)],
             [0, 0, 0, 1]])

        return trans

    def basic_jacobian(self, trans_prev, ee_pose):
        pos_prev = np.array([trans_prev[0, 3], trans_prev[1, 3], trans_prev[2, 3]])
        z_axis_prev = np.array([trans_prev[0, 2], trans_prev[1, 2], trans_prev[2, 2]])

        basic_jacobian = np.hstack((np.cross(z_axis_prev, ee_pose - pos_prev), z_axis_prev))
        return basic_jacobian
        

class NLinkArm:
    def __init__(self, dh_params_list):
        self.link_list = []
        for i in range(len(dh_params_list)):
            self.link_list.append(Link(dh_params_list[i]))

        self.fig = plt.figure()
        self.ax = Axes3D(self.fig)

    def transformation_matrix(self):
        trans = np.identity(4)
        for i in range(len(self.link_list)):
            trans = np.dot(trans, self.link_list[i].transformation_matrix())
        return trans
    
    def forward_kinematics(self):
        trans = self.transformation_matrix()

        x = trans[0, 3]
        y = trans[1, 3]
        z = trans[2, 3]
        alpha = math.atan2(trans[1, 2], trans[1, 3])
        beta = math.atan2(trans[0, 2] * math.cos(alpha) + trans[1, 2] * math.sin(alpha), trans[2, 2])
        gamma = math.atan2(-trans[0, 0] * math.sin(alpha) + trans[1, 0] * math.cos(alpha), -trans[0, 1] * math.sin(alpha) + trans[1, 1] * math.cos(alpha))

        return [x, y, z, alpha, beta, gamma]

    def basic_jacobian(self, ref_ee_pose):
        basic_jacobian_mat = []
        
        trans = np.identity(4)        
        for i in range(len(self.link_list)):
            trans = np.dot(trans, self.link_list[i].transformation_matrix())
            basic_jacobian_mat.append(self.link_list[i].basic_jacobian(trans, ref_ee_pose[0:3]))
            
        #print(np.array(basic_jacobian_mat).T)
        return np.array(basic_jacobian_mat).T

    def inverse_kinematics(self, ref_ee_pose):
        ee_pose = self.forward_kinematics()
        diff_pose = ee_pose - np.array(ref_ee_pose)
        
        for cnt in range(1000):
            basic_jacobian_mat = self.basic_jacobian(ref_ee_pose)
            alpha, beta, gamma = self.calc_euler_angle()
            
            K_zyz = np.array([[0, -math.sin(alpha), math.cos(alpha) * math.sin(beta)],
                              [0, math.cos(alpha), math.sin(alpha) * math.sin(beta)],
                              [1, 0, math.cos(beta)]])
            K_alpha = np.identity(6)
            K_alpha[3:, 3:] = K_zyz

            theta_dot = np.dot(np.dot(np.linalg.pinv(basic_jacobian_mat), K_alpha), np.array(diff_pose))
            self.update_joint_angles(theta_dot)

    def calc_euler_angle(self):
        trans = self.transformation_matrix()
        
        alpha = math.atan2(trans[1][2], trans[0][2])
        beta = math.atan2(trans[0][2] * math.cos(alpha) + trans[1][2] * math.sin(alpha), trans[2][2])
        gamma = math.atan2(-trans[0][0] * math.sin(alpha) + trans[1][0] * math.cos(alpha), -trans[0][1] * math.sin(alpha) + trans[1][1] * math.cos(alpha))
        
        return alpha, beta, gamma
    
    def set_joint_angles(self, joint_angle_list):
        for i in range(len(self.link_list)):
            self.link_list[i].dh_params_[0] = joint_angle_list[i]

    def update_joint_angles(self, diff_joint_angle_list):
        for i in range(len(self.link_list)):
            self.link_list[i].dh_params_[0] += diff_joint_angle_list[i]
        
    def plot(self):
        x_list = []
        y_list = []
        z_list = []

        trans = np.identity(4)
        
        x_list.append(trans[0, 3])
        y_list.append(trans[1, 3])
        z_list.append(trans[2, 3])
        for i in range(len(self.link_list)):
            trans = np.dot(trans, self.link_list[i].transformation_matrix())
            x_list.append(trans[0, 3])
            y_list.append(trans[1, 3])
            z_list.append(trans[2, 3])
            
        self.ax.plot(x_list, y_list, z_list, "o-", color="#00aa00", ms=4, mew=0.5)
        self.ax.plot([0], [0], [0], "o")
        
        self.ax.set_xlim(-1, 1)
        self.ax.set_ylim(-1, 1)
        self.ax.set_zlim(-1, 1)        
        plt.show()
        
if __name__ == "__main__":
    n_link_arm = NLinkArm([[0., -math.pi/2, .1, 0.],
                           [math.pi/2, math.pi/2, 0., 0.],
                           [0., -math.pi/2, 0., .4],
                           [0., math.pi/2, 0., 0.],
                           [0., -math.pi/2, 0., .321],
                           [0., math.pi/2, 0., 0.],
                           [0., 0., 0., 0.]])

    print(n_link_arm.forward_kinematics())
    n_link_arm.set_joint_angles([1, 1, 1, 1, 1, 1, 1])
    n_link_arm.plot()
