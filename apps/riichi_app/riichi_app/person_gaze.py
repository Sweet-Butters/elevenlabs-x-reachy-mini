"""Calibrated, bounded body gaze for the robot camera."""

import time
import math

from reachy_mini.utils import create_head_pose
from reachy_mini.utils.rotation import Rotation


def _clamp(value, limit):
    return max(-limit, min(limit, value))


class PersonGaze:
    def __init__(self, robot, log=False, body=True):
        self.robot = robot
        self.log = log
        self.body = body
        self.yaw = 0.0
        self.body_yaw = 0.0
        self.pitch = -10.0
        self.last_seen = time.monotonic()
        self.last_move = 0.0
        self.last_log = 0.0
        self.off_center_since = None
        self.turning = False
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
            v = 1 if y1 <= 3 else round(y1 + 0.25 * (y2-y1))
            u = max(1, min(width-2, u))
            v = max(1, min(height-2, v))
            pose = self.robot.look_at_image(u, v, perform_movement=False)
            _, pitch, yaw = Rotation.from_matrix(pose[:3, :3]).as_euler("xyz", degrees=True)
            target = (u, v)
            self.last_seen = now
            desired_yaw = _clamp(float(yaw), 75.0 if self.body else 35.0)
            desired_pitch = max(-30.0, min(5.0, float(pitch)))
        elif now - self.last_seen >= 3.0:
            desired_yaw, desired_pitch = 0.0, -10.0
            self.off_center_since = None
            self.turning = False
        else:
            return

        desired_body = self.body_yaw
        if self.body:
            if target is None:
                desired_body = 0.0
            else:
                # The image pose is in the world frame: it already includes the
                # present body and head yaw plus the pixel's angular offset.
                total_yaw = desired_yaw
                if self.turning:
                    if abs(total_yaw) <= 9.0:
                        self.turning = False
                        self.off_center_since = None
                elif abs(total_yaw) >= 14.0:
                    if self.off_center_since is None:
                        self.off_center_since = now
                    elif now - self.off_center_since >= 0.25:
                        self.turning = True
                else:
                    self.off_center_since = None
                if self.turning:
                    candidate = _clamp(0.78 * total_yaw, 55.0)
                    if abs(candidate - self.body_yaw) >= 2.0:
                        desired_body = candidate

        body_delta = desired_body - self.body_yaw
        elapsed = min(0.3, now - self.last_move) if self.last_move else 0.22
        new_body = self.body_yaw + _clamp(body_delta, 50.0 * elapsed)
        # Head pose yaw is in the world frame; the body yaw is passed separately
        # to the SDK's IK. Keep the head within its relative range as body moves.
        desired_yaw = max(new_body - 35.0, min(new_body + 35.0, desired_yaw))
        dy = desired_yaw - self.yaw
        dp = desired_pitch - self.pitch
        if abs(dy) < 1.5 and abs(dp) < 1.5 and abs(body_delta) < 0.5:
            return
        self.yaw += max(-3.5, min(3.5, dy))
        self.pitch += max(-2.5, min(2.5, dp))
        self.yaw = max(new_body - 35.0, min(new_body + 35.0, self.yaw))
        self.body_yaw = new_body
        self.robot.goto_target(head=create_head_pose(yaw=self.yaw, pitch=self.pitch, degrees=True),
                               duration=0.18, body_yaw=math.radians(self.body_yaw) if self.body else None)
        self.last_move = time.monotonic()
        if self.log and now - self.last_log >= 0.5:
            try:
                read = self.robot.get_current_head_pose()
                _, actual_pitch, actual_yaw = Rotation.from_matrix(read[:3, :3]).as_euler("xyz", degrees=True)
                actual_body = math.degrees(self.robot.get_current_joint_positions()[0][0])
                readback = f"readback head={actual_yaw:+.1f} pitch={actual_pitch:+.1f} body={actual_body:+.1f}"
            except Exception as exc:
                readback = f"readback error={exc}"
            print(f"gaze pixel={target} command head={self.yaw:+.1f} pitch={self.pitch:+.1f} "
                  f"body={self.body_yaw:+.1f} {readback}", flush=True)
            self.last_log = now


def neutral(robot):
    robot.disable_wobbling()
    robot.goto_target(head=create_head_pose(pitch=-10, degrees=True), duration=0.8,
                      body_yaw=0.0)
