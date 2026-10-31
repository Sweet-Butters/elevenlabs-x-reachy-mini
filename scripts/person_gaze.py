"""Calibrated, bounded body gaze for the robot camera."""

import time

from reachy_mini.utils import create_head_pose
from reachy_mini.utils.rotation import Rotation


class PersonGaze:
    def __init__(self, robot, log=False):
        self.robot = robot
        self.log = log
        self.yaw = 0.0
        self.pitch = -10.0
        self.last_seen = time.monotonic()
        self.last_move = 0.0
        self.last_log = 0.0
        robot.disable_wobbling()

    def update(self, boxes, width, height):
        now = time.monotonic()
        if now - self.last_move < 0.22:
            return
        target = None
        if boxes:
            box = max(boxes, key=lambda b: max(0, b[2]-b[0]) * max(0, b[3]-b[1]))
            x1, y1, x2, y2 = box
            # A cropped head is usually above the frame; aim just inside its top edge.
            u = round((x1 + x2) / 2)
            v = round(y1 + (0.08 if y1 <= 3 else 0.25) * (y2-y1))
            u = max(1, min(width-2, u))
            v = max(1, min(height-2, v))
            pose = self.robot.look_at_image(u, v, perform_movement=False)
            _, pitch, yaw = Rotation.from_matrix(pose[:3, :3]).as_euler("xyz", degrees=True)
            target = (u, v)
            self.last_seen = now
            desired_yaw = max(-35.0, min(35.0, float(yaw)))
            desired_pitch = max(-20.0, min(5.0, float(pitch)))
        elif now - self.last_seen >= 3.0:
            desired_yaw, desired_pitch = 0.0, -10.0
        else:
            return

        dy = desired_yaw - self.yaw
        dp = desired_pitch - self.pitch
        if abs(dy) < 1.5 and abs(dp) < 1.5:
            return
        self.yaw += max(-3.5, min(3.5, dy))
        self.pitch += max(-2.5, min(2.5, dp))
        self.robot.goto_target(head=create_head_pose(yaw=self.yaw, pitch=self.pitch, degrees=True),
                               duration=0.18, body_yaw=None)
        self.last_move = time.monotonic()
        if self.log and now - self.last_log >= 0.5:
            read = self.robot.get_current_head_pose()
            _, actual_pitch, actual_yaw = Rotation.from_matrix(read[:3, :3]).as_euler("xyz", degrees=True)
            print(f"gaze pixel={target} command yaw={self.yaw:+.1f} pitch={self.pitch:+.1f} "
                  f"readback yaw={actual_yaw:+.1f} pitch={actual_pitch:+.1f}", flush=True)
            self.last_log = now


def neutral(robot):
    robot.disable_wobbling()
    robot.goto_target(head=create_head_pose(pitch=-10, degrees=True), duration=0.8,
                      body_yaw=None)
