from __future__ import division

from copy import deepcopy
from math import ceil
from typing import Any, List, Optional, Tuple

from asciimatics.effects import Effect, Print
from asciimatics.event import Event, KeyboardEvent
from asciimatics.exceptions import StopApplication
# from asciimatics.sprites import Arrow, Plot, Sam
from asciimatics.scene import Scene
from asciimatics.screen import Screen
from asciimatics.renderers import SpeechBubble

MOVEMENT_MAPPINGS = [
    {
        "trigger_keys": (ord("a"), Screen.KEY_LEFT),
        "raycast_direction": (-1, 0),
        "map_movement": ("x", -1),
    },
    {
        "trigger_keys": (ord("d"), Screen.KEY_RIGHT),
        "raycast_direction": (+1, 0),
        "map_movement": ("x", +1),
    },
    {
        "trigger_keys": (ord("w"), Screen.KEY_UP),
        "raycast_direction": (0, -1),
        "map_movement": ("y", -1),
    },
    {
        "trigger_keys": (ord("s"), Screen.KEY_DOWN),
        "raycast_direction": (0, +1),
        "map_movement": ("y", +1),
    },
]


class Map(Effect):
    """
    Draw the map relative to the player position
    and controls the map in general.
    """

    def __init__(self, screen: Screen, game_map: List[str]):
        super(Map, self).__init__(screen)
        self._map: List[str] = deepcopy(game_map)

        for i, line in enumerate(game_map):
            j = line.find('@')
            if j > -1:
                self.player_x = j
                self.player_y = i
                self._map[i] = line.replace('@', ' ')

        self._x = 0
        self._y = 0

        # print(f"player: ({self.player_x},{self.player_y})")
        # print(f"map: ({self._map_x},{self._map_y})")

    def _update(self, _: Any = None) -> None:
        """
        This function is called every frame, here we draw the player centered at the screen
        and the maps surrounding it.
        """
        space_x = self.screen.width
        offset_x = (space_x // 2 - self.player_x, ceil(space_x / 2) + self.player_x)
        space_y = self.screen.height
        offset_y = space_y // 2 - self.player_y

        for i in range(offset_y):
            self.screen.print_at(" "*self.screen.width, 0, i)
        for i, chars in enumerate(self._map):
            chars = " "*offset_x[0] + chars + " "*offset_x[1]
            self.screen.print_at(chars, 0, offset_y + i)
        for i in range(offset_y+len(self._map), self.screen.height):
            self.screen.print_at(" "*self.screen.width, 0, i)

        self.screen.print_at("@", self.screen.width//2, self.screen.height//2)

    @property
    def frame_update_count(self) -> int:
        """Required function for Effects."""
        # No animation required.
        return 0

    @property
    def stop_frame(self) -> int:
        """Required function for Effects."""
        # No specific end point for this Effect.  Carry on running forever.
        return 0

    def reset(self) -> None:
        """Required function for Effects."""
        # Nothing special to do.  Just need this to satisfy the ABC.
        pass


class GameController(Scene):
    """
    Class responsible for moving the player along the map
    and controlling the game in general.
    """
    # Control collisions
    EMPTY_SPACE = 0
    CORRECT_WALL = 1
    WRONG_WALL = 2

    # Control game ending
    WRONG_TAGS = 100
    CORRECT_TAGS = 101
    NOT_FINISHED = 102

    # Here we decide the signal each sprite sends to the game
    SPRITE_MAP = {
        " ": EMPTY_SPACE,
        "X": WRONG_WALL,
        "#": WRONG_WALL,
        "|": WRONG_WALL,
    }

    # Phrases spoken when the character tags walls
    SPEECH = {
        # TODO: we can implement various different speeches
        # and pick one at random
        ord('W'): "Is this the upper wall?",
        ord('S'): "Is this the lower wall?",
        ord('A'): "Is this the left wall?",
        ord('D'): "Is this the right wall?",
    }

    def __init__(self, screen: Screen, level_map: List[str]):
        self._screen = screen
        self._map = Map(screen, level_map)
        effects = [
            self._map,
        ]
        # Walls tagged by the player,
        # if he tags the 4 outer walls correctly
        # he realizes he is in a box and finish the level
        self.tagged_walls = {}
        super(GameController, self).__init__(effects, -1)

    def cast_ray(self, direction: Tuple[int], pos: Optional[List[int]] = None) -> int:
        """
        Cast a ray into 'direction' starting from 'pos';
        if 'pos' is not specified we default to player pos.
        """

        if pos is None:
            pos = [self._map.player_x, self._map.player_y]

        x = direction[0] + pos[0]
        y = direction[1] + pos[1]

        # If we tag the border of the map, we've hit the right wall
        if x in (0, len(self._map._map[0])-1) or \
                y in (0, len(self._map._map)-1):
            return GameController.CORRECT_WALL

        # If not we send the information of that location
        return GameController.SPRITE_MAP[self._map._map[y][x]]

    def speak(self, text: str, duration=20):
        """Text to be spoken by the character"""
        linebreaks = text.count('\n')
        self.add_effect(
            Print(
                self._screen,
                SpeechBubble(text, "L"),
                self._screen.height // 2 - 4 - linebreaks,
                self._screen.width // 2 + 2,
                transparent=False,
                clear=True, delete_count=duration)
        )

    def check_level_completion(self) -> int:
        """
        Check if the player finished the level
        How it works:
        1 - If the player has not tagged the 4 walls (up, down,left, right)
            we return NOT_FINISHED so he can keep playing
        2 - If he tagged all 4 walls but at least 1 is wrong we return
            WRONG_TAGS, he will receive a message that he is wrong and have to guess again
        3 - If he tagged everything right, he gets CORRECT_TAGS and ends the level
        """

        values = ('r', 'd', 'l', 'r')
        res = GameController.CORRECT_TAGS
        for direction in values:
            if direction not in self.tagged_walls:
                return GameController.NOT_FINISHED
            if self.tagged_walls[direction] == False:
                res = GameController.WRONG_TAGS

        return res

    def process_event(self, event: Event) -> Optional[Event]:
        """Process events, mostly player input."""
        # Allow standard event processing first
        if super(GameController, self).process_event(event) is None:
            return

        # If that didn't handle it, check for a key that this demo understands.
        if isinstance(event, KeyboardEvent):
            key_code = event.key_code
            speech = None
            not_recognised = True  # Flag for if the key code wasn't recognised

            if key_code in (ord("q"), ord("Q")):
                raise StopApplication("User exit")

            for movement_mapping in MOVEMENT_MAPPINGS:
                if key_code in movement_mapping["trigger_keys"]:
                    if (
                            self.cast_ray(movement_mapping["raycast_direction"])
                            == GameController.EMPTY_SPACE
                    ):
                        axis, move = movement_mapping["map_movement"]
                        attr = (self._map, f"player_{axis}")
                        setattr(*attr, getattr(*attr) + move)

                    not_recognised = False
                    break

            # TODO: refactor this later
            if key_code == ord("A"):
                collision = self.cast_ray((-1, 0))
                if collision == GameController.WRONG_WALL:
                    self.tagged_walls['l'] = False
                    speech = GameController.SPEECH[key_code]
                if collision == GameController.CORRECT_WALL:
                    self.tagged_walls['l'] = True
                    speech = GameController.SPEECH[key_code]

            if key_code == ord("D"):
                collision = self.cast_ray((1, 0))
                if collision == GameController.WRONG_WALL:
                    self.tagged_walls['r'] = False
                    speech = GameController.SPEECH[key_code]
                if collision == GameController.CORRECT_WALL:
                    self.tagged_walls['r'] = True
                    speech = GameController.SPEECH[key_code]

            if key_code == ord("W"):
                collision = self.cast_ray((0, -1))
                if collision == GameController.WRONG_WALL:
                    self.tagged_walls['u'] = False
                    speech = GameController.SPEECH[key_code]
                if collision == GameController.CORRECT_WALL:
                    self.tagged_walls['u'] = True
                    speech = GameController.SPEECH[key_code]

            if key_code == ord("S"):
                collision = self.cast_ray((0, 1))
                if collision == GameController.WRONG_WALL:
                    self.tagged_walls['d'] = False
                    speech = GameController.SPEECH[key_code]
                if collision == GameController.CORRECT_WALL:
                    self.tagged_walls['d'] = True
                    speech = GameController.SPEECH[key_code]

            check = self.check_level_completion()

            if check == GameController.CORRECT_TAGS:
                self.speak("I Knew it!\nI was in a box all along!")
                # TODO: finish the level, perhaps put some animation
                # and load the next
                # self.load_next_level()
                self.tagged_walls = {}
            elif check == GameController.WRONG_TAGS:
                self.speak("Hmm... I don't think this is right.")
                self.tagged_walls = {}
            elif check == GameController.NOT_FINISHED:
                if speech is not None:
                    self.speak(speech)

            if not_recognised:
                # Not a recognised key - pass on to other handlers.
                return event

        else:
            # Ignore other types of events.
            return event
