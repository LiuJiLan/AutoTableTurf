import copy
from datetime import datetime
from time import sleep
from typing import List, Optional

import cv2
import numpy as np

from capture import Capture
from controller import Controller
from logger import logger
from tableturf.ai import AI
from tableturf.debugger.interface import Debugger
from tableturf.manager import action
from tableturf.manager import detection
from tableturf.manager.data import Stats, Result
from tableturf.model import Status, Card, Step, Stage


class Exit:
    def __init__(self, max_win: Optional[int] = None, max_battle: Optional[int] = None, max_time: Optional[int] = None):
        self.__max_win = max_win
        self.__max_battle = max_battle
        self.__max_time = max_time

    def exit(self, stats: Stats) -> bool:
        if self.__max_win is not None and self.__max_win <= stats.win:
            return True
        if self.__max_battle is not None and self.__max_battle <= stats.battle:
            return True
        if self.__max_time is not None and self.__max_time <= stats.time:
            return True
        return False


class TableTurfManager:
    @staticmethod
    def __resize(capture_fn):
        """
        Resize the captured image to (1920, 1080) to ensure that ROIs work correctly.
        """

        def wrapper():
            img = capture_fn()
            height, width, _ = img.shape
            if height != 1080 or width != 1920:
                img = cv2.resize(img, (1920, 1080))
            return img

        return wrapper

    @staticmethod
    def __equal(a, b) -> bool:
        if isinstance(a, np.ndarray) and isinstance(b, np.ndarray):
            return np.all(a == b)
        else:
            return a == b

    def __multi_detect(self, detect_fn, sleep_time=0.1, max_loop=100):
        def wrapper(*args, **kwargs):
            previous = detect_fn(self.__capture(), *args, **kwargs)
            for _ in range(max_loop):
                sleep(sleep_time)
                current = detect_fn(self.__capture(), *args, **kwargs)
                if isinstance(previous, tuple) and isinstance(current, tuple):
                    if len(previous) == len(current) and np.all([self.__equal(a, b) for a, b in zip(previous, current)]):
                        return current
                elif current == previous:
                    return current
                previous = current
            logger.warn(f'tableturf.multi_detect: exceeded the maximum number of loops')
            return previous

        return wrapper

    def __init__(self, capture: Capture, controller: Controller, ai: AI, debugger: Optional[Debugger] = None):
        self.__capture = self.__resize(capture.capture)
        self.__controller = controller
        self.__ai = ai
        self.__debugger = debugger
        self.stats = Stats()
        self.__session = dict()

    def run(self, deck: int, stage: Optional[Stage] = None, his_deck: Optional[List[Card]] = None, closer: Exit = Exit(), debug=False):
        self.__session = {
            'empty_stage': stage,
            'his_deck': his_deck,
            'debug': self.__debugger if debug else None,
        }
        self.stats.start_time = datetime.now().timestamp()
        while True:
            self.__select_deck(deck)
            self.__redraw()
            self.__init_roi()
            for round in range(12, 0, -1):
                status = self.__get_status(round)
                step = self.__ai.next_step(status)
                self.__move(status, step)
            result = self.__get_result()
            self.__update_stats(result)
            close = closer.exit(self.stats)
            self.__close(close)
            if close:
                break

    def __select_deck(self, deck: int):
        target = deck
        while True:
            current = self.__multi_detect(detection.deck_cursor)(debug=self.__session['debug'])
            if current == target:
                break
            if current != -1:
                macro = action.move_deck_cursor_marco(target, current)
                self.__controller.macro(macro)
            else:
                sleep(0.5)
        deck = self.__multi_detect(detection.deck)(debug=self.__session['debug'])
        self.__session['my_deck'] = deck
        self.__controller.press_buttons([Controller.Button.A])
        self.__controller.press_buttons([Controller.Button.A])  # in case command is lost

    def __redraw(self):
        while self.__multi_detect(detection.redraw_cursor)(debug=self.__session['debug']) == -1:
            sleep(0.5)
        hands = self.__multi_detect(detection.hands)(debug=self.__session['debug'])
        stage = self.__session['empty_stage']
        my_deck, his_deck = self.__session['my_deck'], self.__session['his_deck']
        my_remaining_deck = copy.deepcopy(my_deck)
        for card in hands:
            try:
                my_remaining_deck.remove(card)
            except ValueError:
                pass
        redraw = self.__ai.redraw(hands, stage, my_remaining_deck, his_deck)
        target = 1 if redraw else 0
        while True:
            current = self.__multi_detect(detection.redraw_cursor)(debug=self.__session['debug'])
            if current == target:
                break
            macro = action.move_redraw_cursor_marco(target, current)
            self.__controller.macro(macro)
        self.__controller.press_buttons([Controller.Button.A])
        self.__controller.press_buttons([Controller.Button.A])  # in case command is lost

    def __init_roi(self):
        while self.__multi_detect(detection.hands_cursor)(debug=self.__session['debug']) == -1:
            sleep(0.5)
        rois, roi_width, roi_height = detection.stage_rois(self.__capture(), debug=self.__session['debug'])
        self.__session['rois'] = rois
        self.__session['roi_width'] = roi_width
        self.__session['roi_height'] = roi_height
        self.__session['last_stage'] = None
        stage = self.__multi_detect(detection.stage)(rois=rois, roi_width=roi_width, roi_height=roi_height, last_stage=None, debug=self.__session['debug'])
        self.__session['empty_stage'] = stage

    def __get_status(self, round: int) -> Status:
        my_deck, his_deck = self.__session['my_deck'], self.__session['his_deck']
        while self.__multi_detect(detection.hands_cursor)(debug=self.__session['debug']) == -1:
            # TODO: update his deck here
            sleep(0.5)
        rois, roi_width, roi_height, last_stage = self.__session['rois'], self.__session['roi_width'], self.__session['roi_height'], self.__session['last_stage']
        stage = self.__multi_detect(detection.stage)(rois=rois, roi_width=roi_width, roi_height=roi_height, last_stage=last_stage, debug=self.__session['debug'])
        self.__session['last_stage'] = stage
        hands = self.__multi_detect(detection.hands)(debug=self.__session['debug'])
        for card in hands:
            try:
                my_deck.remove(card)
            except ValueError:
                pass
        self.__session['my_deck'] = my_deck
        my_sp, his_sp = self.__multi_detect(detection.sp)(debug=self.__session['debug'])
        return Status(stage=stage, hands=hands, round=round, my_sp=my_sp, his_sp=his_sp, my_deck=my_deck, his_deck=his_deck)

    def __move_hands_cursor(self, target):
        while True:
            current = self.__multi_detect(detection.hands_cursor)(debug=self.__session['debug'])
            if current == target:
                break
            macro = action.move_hands_cursor_marco(target, current)
            self.__controller.macro(macro)

    def __move(self, status: Status, step: Step):
        if step.action == step.Action.Skip:
            self.__move_hands_cursor(4)
            while not self.__multi_detect(detection.skip)(debug=self.__session['debug']):
                self.__controller.press_buttons([Controller.Button.A])
            self.__move_hands_cursor(status.hands.index(step.card))
            self.__controller.press_buttons([Controller.Button.A])
            self.__controller.press_buttons([Controller.Button.A])  # in case command is lost
            return

        if step.action == step.Action.SpecialAttack:
            self.__move_hands_cursor(5)
            while not self.__multi_detect(detection.special_on)(debug=self.__session['debug']):
                self.__controller.press_buttons([Controller.Button.A])
        # select card
        self.__move_hands_cursor(status.hands.index(step.card))
        expected_preview = step.card.get_pattern(0)
        while True:
            self.__controller.press_buttons([Controller.Button.A])
            preview, current_index = self.__multi_detect(detection.preview)(stage=status.stage, rois=self.__session['rois'], roi_width=self.__session['roi_width'], roi_height=self.__session['roi_height'], debug=self.__session['debug'])
            if action.compare_pattern(preview, expected_preview):
                break
        # rotate card
        if step.rotate > 0:
            target_rotate = step.rotate
            all_patterns = [step.card.get_pattern(i) for i in range(4)]
            while True:
                actual, _ = self.__multi_detect(detection.preview)(stage=status.stage, rois=self.__session['rois'], roi_width=self.__session['roi_width'], roi_height=self.__session['roi_height'], debug=self.__session['debug'])
                current_rotate = np.argmax([pattern == actual for pattern in all_patterns])
                if current_rotate == 0 and all_patterns[0] != actual:
                    current_rotate = np.argmax([action.compare_pattern(pattern, actual) for pattern in all_patterns])
                rotate = (target_rotate + 4 - current_rotate) % 4
                logger.debug(f'tableturf.rotate: current_rotate={current_rotate}, target_rotate={target_rotate}, step={rotate}')
                if rotate == 0:
                    break
                macro = action.rotate_card_marco(rotate)
                self.__controller.macro(macro)
        # move card
        expected_preview = step.card.get_pattern(step.rotate)
        while True:
            while True:
                preview, current_index = self.__multi_detect(detection.preview)(stage=status.stage, rois=self.__session['rois'], roi_width=self.__session['roi_width'], roi_height=self.__session['roi_height'], debug=self.__session['debug'])
                if action.compare_pattern(preview, expected_preview):
                    break
            macro = action.move_card_marco(current_index, preview, status.stage, step)
            if macro.strip() != '':
                self.__controller.macro(macro)
            else:
                break
        self.__controller.press_buttons([Controller.Button.A])
        self.__controller.press_buttons([Controller.Button.A])  # in case command is lost

    def __get_result(self) -> Result:
        # TODO
        sleep(12)
        img = self.__capture()
        return Result(0, 0)

    def __update_stats(self, result: Result):
        if result.my_ink > result.his_ink:
            self.stats.win += 1
        now = datetime.now().timestamp()
        self.stats.time = now - self.stats.start_time
        self.stats.battle += 1
        logger.debug(f'tableturf.update_stats: stats={self.stats}')

    def __close(self, close: bool):
        self.__controller.press_buttons([Controller.Button.A])
        self.__controller.press_buttons([Controller.Button.A])  # in case command is lost
        target = 0 if close else 1
        count = 0
        while True:
            current = self.__multi_detect(detection.replay_cursor)(debug=self.__session['debug'])
            if current == target:
                break
            if current != -1:
                macro = action.move_replay_cursor_marco(target, current)
                self.__controller.macro(macro)
            else:
                sleep(0.5)
            # press A when unlock new items
            count = (count + 1) % 6
            if count == 0:
                self.__controller.press_buttons([Controller.Button.A])
        self.__controller.press_buttons([Controller.Button.A])
        self.__controller.press_buttons([Controller.Button.A])  # in case command is lost
