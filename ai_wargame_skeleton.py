from __future__ import annotations
import argparse
import copy
from collections import deque, defaultdict
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from time import sleep
from typing import Tuple, Iterable, ClassVar, List, Optional
import random
import requests

PARENT = 0
ID = 0

current_node_id = 0
time_limit_exceeded = False
start_time = 0
last_algo_time = 0
time_ratio = 0
time_elapsed_last_move = 0

# maximum and minimum values for our heuristic scores (usually represents an end of game condition)
MAX_HEURISTIC_SCORE = 2000000000
MIN_HEURISTIC_SCORE = -2000000000

ID = 0


class UnitType(Enum):
    """Every unit type."""
    AI = 0
    Tech = 1
    Virus = 2
    Program = 3
    Firewall = 4


class Player(Enum):
    """The 2 players."""
    Attacker = 0
    Defender = 1

    def next(self) -> Player:
        """The next (other) player."""
        if self is Player.Attacker:
            return Player.Defender
        else:
            return Player.Attacker


class GameType(Enum):
    AttackerVsDefender = 0
    AttackerVsComp = 1
    CompVsDefender = 2
    CompVsComp = 3


##############################################################################################################


@dataclass(slots=True)
class Unit:
    player: Player = Player.Attacker
    type: UnitType = UnitType.Program
    health: int = 9
    # class variable: damage table for units (based on the unit type constants in order)
    damage_table: ClassVar[list[list[int]]] = [
        [3, 3, 3, 3, 1],  # AI
        [1, 1, 6, 1, 1],  # Tech
        [9, 6, 1, 6, 1],  # Virus
        [3, 3, 3, 3, 1],  # Program
        [1, 1, 1, 1, 1],  # Firewall
    ]
    # class variable: repair table for units (based on the unit type constants in order)
    repair_table: ClassVar[list[list[int]]] = [
        [0, 1, 1, 0, 0],  # AI
        [3, 0, 0, 3, 3],  # Tech
        [0, 0, 0, 0, 0],  # Virus
        [0, 0, 0, 0, 0],  # Program
        [0, 0, 0, 0, 0],  # Firewall
    ]

    def is_alive(self) -> bool:
        """Are we alive ?"""
        return self.health > 0

    def mod_health(self, health_delta: int):
        """Modify this unit's health by delta amount."""
        self.health += health_delta
        if self.health < 0:
            self.health = 0
        elif self.health > 9:
            self.health = 9

    def to_string(self) -> str:
        """Text representation of this unit."""
        p = self.player.name.lower()[0]
        t = self.type.name.upper()[0]
        return f"{p}{t}{self.health}"

    def __str__(self) -> str:
        """Text representation of this unit."""
        return self.to_string()

    def damage_amount(self, target: Unit) -> int:
        """How much can this unit damage another unit."""
        amount = self.damage_table[self.type.value][target.type.value]
        if target.health - amount < 0:
            return target.health
        return amount

    def repair_amount(self, target: Unit) -> int:
        """How much can this unit repair another unit."""
        amount = self.repair_table[self.type.value][target.type.value]
        if target.health + amount > 9:
            return 9 - target.health
        return amount


##############################################################################################################

@dataclass(slots=True)
class Coord:
    """Representation of a game cell coordinate (row, col)."""
    row: int = 0
    col: int = 0

    def col_string(self) -> str:
        """Text representation of this Coord's column."""
        coord_char = '?'
        if self.col < 16:
            coord_char = "0123456789abcdef"[self.col]
        return str(coord_char)

    def row_string(self) -> str:
        """Text representation of this Coord's row."""
        coord_char = '?'
        if self.row < 26:
            coord_char = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[self.row]
        return str(coord_char)

    def to_string(self) -> str:
        """Text representation of this Coord."""
        return self.row_string() + self.col_string()

    def __str__(self) -> str:
        """Text representation of this Coord."""
        return self.to_string()

    def clone(self) -> Coord:
        """Clone a Coord."""
        return copy.copy(self)

    def iter_range(self, dist: int) -> Iterable[Coord]:
        """Iterates over Coords inside a rectangle centered on our Coord."""
        for row in range(self.row - dist, self.row + 1 + dist):
            for col in range(self.col - dist, self.col + 1 + dist):
                yield Coord(row, col)

    def iter_adjacent(self) -> Iterable[Coord]:
        """Iterates over adjacent Coords."""
        yield Coord(self.row - 1, self.col)
        yield Coord(self.row, self.col - 1)
        yield Coord(self.row + 1, self.col)
        yield Coord(self.row, self.col + 1)

    def euclidean_distance_to(self, other):
        dx = other.col - self.col
        dy = other.row - self.row
        return (dx ** 2 + dy ** 2) ** 0.5

    # Method added by our team
    def iter_all8_adjacent(self) -> Iterable[Coord]:
        """Iterates over all 8 adjacent coordinates including diagonals."""

        # Check all 8 directions
        yield Coord(self.row - 1, self.col)
        yield Coord(self.row + 1, self.col)
        yield Coord(self.row, self.col - 1)
        yield Coord(self.row, self.col + 1)

        yield Coord(self.row - 1, self.col - 1)
        yield Coord(self.row - 1, self.col + 1)
        yield Coord(self.row + 1, self.col - 1)
        yield Coord(self.row + 1, self.col + 1)

    @classmethod
    def from_string(cls, s: str) -> Coord | None:
        """Create a Coord from a string. ex: D2."""
        s = s.strip()
        for sep in " ,.:;-_":
            s = s.replace(sep, "")
        if (len(s) == 2):
            coord = Coord()
            coord.row = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".find(s[0:1].upper())
            coord.col = "0123456789abcdef".find(s[1:2].lower())
            return coord
        else:
            return None


##############################################################################################################

@dataclass(slots=True)
class CoordPair:
    """Representation of a game move or a rectangular area via 2 Coords."""
    src: Coord = field(default_factory=Coord)
    dst: Coord = field(default_factory=Coord)

    def to_string(self) -> str:
        """Text representation of a CoordPair."""
        return self.src.to_string() + " " + self.dst.to_string()

    def __str__(self) -> str:
        """Text representation of a CoordPair."""
        return self.to_string()

    def clone(self) -> CoordPair:
        """Clones a CoordPair."""
        return copy.copy(self)

    def iter_rectangle(self) -> Iterable[Coord]:
        """Iterates over cells of a rectangular area."""
        for row in range(self.src.row, self.dst.row + 1):
            for col in range(self.src.col, self.dst.col + 1):
                yield Coord(row, col)

    @classmethod
    def from_quad(cls, row0: int, col0: int, row1: int, col1: int) -> CoordPair:
        """Create a CoordPair from 4 integers."""
        return CoordPair(Coord(row0, col0), Coord(row1, col1))

    @classmethod
    def from_dim(cls, dim: int) -> CoordPair:
        """Create a CoordPair based on a dim-sized rectangle."""
        return CoordPair(Coord(0, 0), Coord(dim - 1, dim - 1))

    @classmethod
    def from_string(cls, s: str) -> CoordPair | None:
        """Create a CoordPair from a string. ex: A3 B2"""
        s = s.strip()
        for sep in " ,.:;-_":
            s = s.replace(sep, "")
        if (len(s) == 4):
            coords = CoordPair()
            coords.src.row = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".find(s[0:1].upper())
            coords.src.col = "0123456789abcdef".find(s[1:2].lower())
            coords.dst.row = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".find(s[2:3].upper())
            coords.dst.col = "0123456789abcdef".find(s[3:4].lower())
            return coords
        else:
            return None


##############################################################################################################

@dataclass(slots=True)
class Options:
    """Representation of the game options."""
    dim: int = 5
    max_depth: int | None = 4
    min_depth: int | None = 2
    max_time: float | None = 5.0
    game_type: GameType = GameType.AttackerVsDefender
    alpha_beta: bool | None = True
    max_turns: int | None = 100
    randomize_moves: bool = False  # only for D1
    broker: str | None = None


##############################################################################################################

@dataclass(slots=True)
class Stats:
    """Representation of the global game statistics."""
    evaluations_per_depth: dict[int, int] = field(default_factory=dict)
    total_seconds: float = 0.0


##############################################################################################################

class TreeNode:
    def __init__(self, id: int, game: Game, move: CoordPair, e1: int = None, e2: int = None, max=False,
                 depth: int = None):
        self.id = id
        self.game = game
        self.move = move
        self.e1 = e1  # any heuristic for simple minimax, or beta for e2 beta pruning
        self.e2 = e2  # strong heuristic for e2 beta pruning
        self.children: List[TreeNode] = []
        self.max = max  # max = asc order, min = desc order
        self.depth = depth


def _sort_nodes(nodes, reverse):
    # Find the node with the maximum or minimum e1 value based on the reverse flag
    key_node = max(nodes, key=lambda x: x.e1) if reverse else min(nodes, key=lambda x: x.e1)

    # Remove the key_node from the original list and place it at the beginning
    nodes.remove(key_node)
    nodes.insert(0, key_node)

    return nodes


##############################################################################################################

class Tree:
    def __init__(self):
        self.root = None
        self.nodes = {}
        self.stats = {}
        self.total_evals = 0
        self.depth = 0

    def add_node(self, id: int, game: Game, move: CoordPair = None, e1: int = None, e2: int = None,
                 parent: TreeNode = None):
        max_value = parent is None or not self.nodes[parent].max  # sets if its maximizing or minimizing
        node = TreeNode(id, game, move, e1=e1, e2=e2, max=max_value)
        self.nodes[id] = node

        if parent is None:
            self.root = node
            node.depth = 1  # Root node, starting depth of tree at 1
        else:
            parent_node = self.nodes[parent]
            node.depth = self.nodes[parent].depth + 1
            parent_node.children.append(node)

    # Sort level by level from the root to the leafs
    def traverse_ordered(self, node=None):
        if node is None:
            node = self.root

        children = node.children

        if len(children) != 0:
            if children[0].max:
                children = _sort_nodes(children, reverse=False)
            else:
                children = _sort_nodes(children, reverse=True)

        for child in children:
            self.traverse_ordered(child)

        # Update the node children with the sorted values
        node.children = children

    def minimax(self, node=None):
        # If not given, starting node is root
        if node is None:
            node = self.root

        # Check if the node is a leaf node (no need to do any minmax on leaf)
        if not node.children:
            self.calculate_evaluations(node.depth)
            node.e1 = node.game.heuristic_1()  # change call to heuristic here
            return node.e1, None

        if node.max:
            max_value = float("-inf")
            max_child = None
            for child in node.children:
                child_value, _ = self.minimax(child)  # Recursively call minimax
                if child_value > max_value:  # Update the maximum value and its corresponding child
                    max_value = child_value
                    max_child = child
            node.e1 = max_value
            return max_value, max_child

        else:
            min_value = float("inf")
            min_child = None
            for child in node.children:
                child_value, _ = self.minimax(child)
                if child_value < min_value:
                    min_value = child_value
                    min_child = child
            node.e1 = min_value
            return min_value, min_child

    def calculate_evaluations(self, depth: int):  # temp_evals: int
        self.total_evals += 1
        self.stats[depth] = self.stats.get(depth, 0) + 1

    def alpha_beta_pruning(self, node=None):
        # If not given, starting node is root
        if node is None:
            node = self.root

        # Private helper method with initial alpha and beta values
        e2, best_node = self._alpha_beta_pruning(node, float("-inf"), float("inf"))
        return e2, best_node

    def _alpha_beta_pruning(self, node, alpha, beta):
        if not node.children:  # Leaf node
            self.calculate_evaluations(node.depth)
            node.e2 = node.game.heuristic_2()
            return node.e2, node

        if node.max:
            best_node = None
            for child in node.children:
                new_alpha, _ = self._alpha_beta_pruning(child, alpha, beta)  # Recursive call
                if new_alpha > alpha:  # Update the alpha value and its corresponding child
                    alpha = new_alpha
                    best_node = child
                if beta <= alpha:
                    break  # Pruning here
            node.e2 = alpha
            return alpha, best_node
        else:
            best_node = None  # Node that results in the best beta value
            for child in node.children:
                new_beta, _ = self._alpha_beta_pruning(child, alpha, beta)
                if new_beta < beta:
                    beta = new_beta
                    best_node = child
                if beta <= alpha:
                    break  # Pruning here
            node.e2 = beta
            return beta, best_node

    # only for debugging
    def print_tree_to_file(self, file_path, node=None, prefix="", is_last=True):
        if node is None:
            node = self.root

        node_type = "(max)" if node.max else "(min)"
        with open(file_path, 'a') as file:
            file.write(
                prefix + ("└── " if is_last else "├── ") + str(node.depth) + " " + str(
                    node.id) + " " + node_type + "\n")

        if node.children:
            for i, child in enumerate(node.children):
                self.print_tree_to_file(file_path, child, prefix + ("    " if is_last else "│   "),
                                        i == len(node.children) - 1)

    def print_tree_to_file_alphabeta(self, file_path, node=None, prefix="", is_last=True):
        if node is None:
            node = self.root

        node_type = "(+)" if node.max else "(-)"
        e2_str = "None" if node.e2 is None else "{:.2f}".format(node.e2)
        e1_str = "None" if node.e1 is None else "{:.2f}".format(node.e1)

        with open(file_path, 'a') as file:
            file.write(
                prefix + ("└── " if is_last else "├── ") + e2_str + " e1:" + e1_str + " " + node_type + "\n")

        if node.children:
            for i, child in enumerate(node.children):
                self.print_tree_to_file_alphabeta(file_path, child, prefix + ("    " if is_last else "│   "),
                                                  i == len(node.children) - 1)


##############################################################################################################
@dataclass(slots=True)
class Game:
    """Representation of the game state."""
    board: list[list[Unit | None]] = field(default_factory=list)
    next_player: Player = Player.Attacker
    turns_played: int = 0
    options: Options = field(default_factory=Options)
    stats: Stats = field(default_factory=Stats)
    _attacker_has_ai: bool = True
    _defender_has_ai: bool = True

    def __post_init__(self):
        """Automatically called after class init to set up the default board state."""
        dim = self.options.dim
        self.board = [[None for _ in range(dim)] for _ in range(dim)]
        md = dim - 1
        self.set(Coord(0, 0), Unit(player=Player.Defender, type=UnitType.AI))
        self.set(Coord(1, 0), Unit(player=Player.Defender, type=UnitType.Tech))
        self.set(Coord(0, 1), Unit(player=Player.Defender, type=UnitType.Tech))
        self.set(Coord(2, 0), Unit(player=Player.Defender, type=UnitType.Firewall))
        self.set(Coord(0, 2), Unit(player=Player.Defender, type=UnitType.Firewall))
        self.set(Coord(1, 1), Unit(player=Player.Defender, type=UnitType.Program))
        self.set(Coord(md, md), Unit(player=Player.Attacker, type=UnitType.AI))
        self.set(Coord(md - 1, md), Unit(player=Player.Attacker, type=UnitType.Virus))
        self.set(Coord(md, md - 1), Unit(player=Player.Attacker, type=UnitType.Virus))
        self.set(Coord(md - 2, md), Unit(player=Player.Attacker, type=UnitType.Program))
        self.set(Coord(md, md - 2), Unit(player=Player.Attacker, type=UnitType.Program))
        self.set(Coord(md - 1, md - 1), Unit(player=Player.Attacker, type=UnitType.Firewall))

    def clone(self) -> Game:
        """Make a new copy of a game for minimax recursion.

        Shallow copy of everything except the board (options and stats are shared).
        """
        new = copy.copy(self)
        new.board = copy.deepcopy(self.board)
        return new

    def is_empty(self, coord: Coord) -> bool:
        """Check if contents of a board cell of the game at Coord is empty (must be valid coord)."""
        return self.board[coord.row][coord.col] is None

    def get(self, coord: Coord) -> Unit | None:
        """Get contents of a board cell of the game at Coord."""
        if self.is_valid_coord(coord):
            return self.board[coord.row][coord.col]
        else:
            return None

    def set(self, coord: Coord, unit: Unit | None):
        """Set contents of a board cell of the game at Coord."""
        if self.is_valid_coord(coord):
            self.board[coord.row][coord.col] = unit

    def remove_dead(self, coord: Coord):
        """Remove unit at Coord if dead."""
        unit = self.get(coord)
        if unit is not None and not unit.is_alive():
            self.set(coord, None)
            if unit.type == UnitType.AI:
                if unit.player == Player.Attacker:
                    self._attacker_has_ai = False
                else:
                    self._defender_has_ai = False

    def mod_health(self, coord: Coord, health_delta: int):
        """Modify health of unit at Coord (positive or negative delta)."""
        target = self.get(coord)
        if target is not None:
            target.mod_health(health_delta)
            self.remove_dead(coord)

    """CODE MODIFIED OR ADDED BY OUR TEAM FOR D1"""

    def is_valid_move(self, coords: CoordPair) -> Tuple[bool, str, Optional[str]]:

        # if source coordinates are not valid or destination coordinates are not valid, false
        # is_valid_coord checks if coordinate is within board dimensions
        if not self.is_valid_coord(coords.src) or not self.is_valid_coord(coords.dst):
            return False, "Invalid move", "Sorry, src or dest not on board"

        src = self.get(coords.src)
        dst = self.get(coords.dst)

        # if src is empty, return false
        if src is None or self.is_empty(coords.src):
            return False, "Invalid move", "Sorry, source is empty, no player found at location."

        # if player is not the player that should be playing, false
        if src.player != self.next_player:
            return False, "Invalid move", "Sorry, this is " + self.next_player.name + "'s turn."

        # if src and dst is the same, player is self-destructing, return true and indicate that it is a self-destruct
        if not self.is_empty(coords.dst) and coords.src == coords.dst:
            return True, "self-destruct", None

        # if dst is not adjacent, return false
        if coords.dst not in coords.src.iter_adjacent():
            return False, "Invalid move", "Sorry, this destination is not adjacent to the source."

        # if src is AI and player is repairing his own Tech or Virus with health level less than 9,
        # return true and indicate that it is a repair, else return false
        if src.type == UnitType.AI and not self.is_empty(coords.dst) and dst.player == src.player:
            if (dst.type == UnitType.Tech or dst.type == UnitType.Virus) and dst.health < 9:
                return True, "repair", None
            else:
                return False, "Invalid move", "Sorry, AI cannot repair player " + dst.player.name + "."

        # if src is AI, Firewall or Program and is trying to move while engaged in combat (has an opponent adjacent), return false
        # if src is attacking, return true and indicate that it is an attack
        if src.type == UnitType.AI or src.type == UnitType.Firewall or src.type == UnitType.Program:
            if not self.is_empty(coords.dst) and dst.player != src.player:
                return True, "attack", None
            # loop over the return of the iter_adjacent to see if player is engaged in combat
            else:
                for adjacent_coordinate in coords.src.iter_adjacent():
                    if self.is_valid_coord(adjacent_coordinate) and not self.is_empty(adjacent_coordinate) and self.get(
                            adjacent_coordinate).player != src.player:
                        return False, "Invalid move", "Sorry, this player is engaged in combat."

        # if src is Tech or Virus, player can move regardless of being in combat
        # if dst is not empty, src may be attacking, but Tech might also be repairing
        if src.type == UnitType.Tech or src.type == UnitType.Virus:
            if not self.is_empty(coords.dst):
                if dst.player != src.player:
                    return True, "attack", None

                # if src is Tech, player can repair his own team if health is less than 9, otherwise return false
                elif src.type == UnitType.Tech and dst.player == src.player:
                    if (
                            dst.type == UnitType.AI or dst.type == UnitType.Firewall or dst.type == UnitType.Program) and dst.health < 9:
                        return True, "repair", None
                else:
                    return False, "Invalid move", "Sorry, cannot repair, health is already maxed out"

        # if src is an attacker, AI, Firewall and Program can only move up or left; its Tech and Virus can move all directions
        if src.player == Player.Attacker:
            if src.type == UnitType.AI or src.type == UnitType.Firewall or src.type == UnitType.Program:
                if coords.src.row < coords.dst.row or coords.src.col < coords.dst.col:
                    return False, "Invalid move", "An attacker piece of type " + src.type.name + " can only move up or left"

        # if unit is a defender, AI, Firewall and Program can only move down or right; its Tech and Virus can move all directions
        if src.player == Player.Defender:
            if src.type == UnitType.AI or src.type == UnitType.Firewall or src.type == UnitType.Program:
                if coords.src.row > coords.dst.row or coords.src.col > coords.dst.col:
                    return False, "Invalid move", "A defender piece of type: " + src.type.name + " can only move down or right"

        return dst is None, "valid move", None

    def perform_attack(self, coords: CoordPair):
        src = self.get(coords.src)
        dst = self.get(coords.dst)
        dstDamage = src.damage_table[src.type.value][dst.type.value]
        srcDamage = src.damage_table[dst.type.value][src.type.value]
        self.mod_health(coords.src, -srcDamage)
        self.mod_health(coords.dst, -dstDamage)

    def perform_repair(self, coords: CoordPair):
        src = self.get(coords.src)
        dst = self.get(coords.dst)
        repair = src.repair_table[src.type.value][dst.type.value]
        self.mod_health(coords.dst, repair)

    def perform_self_destruction(self, coords: CoordPair):
        self.mod_health(coords.src, -self.get(coords.src).health)
        for adjacent_coordinate in coords.src.iter_all8_adjacent():
            if self.is_valid_coord(adjacent_coordinate) and not self.is_empty(adjacent_coordinate):
                self.mod_health(adjacent_coordinate, -2)

    def log_move(self, move_type, coords: CoordPair):
        with open("gameTrace-<" + str(self.options.alpha_beta) + ">-<" + str(self.options.max_time) + ">-<" + str(
                self.options.max_turns) + ">.txt", "a", encoding="utf-8") as file:

            file.write("\nTurn number: " + str(self.turns_played) + "\n")
            if self.next_player == Player.Attacker:
                file.write("Attacker's Turn\n")
            else:
                file.write("Defender's Turn\n")

            if self.next_player == Player.Attacker and move_type == "valid move":
                file.write("Attacker moved from " + str(coords.src) + " to " + str(coords.dst) + "\n")
            elif self.next_player == Player.Defender and move_type == "valid move":
                file.write("Defender moved from " + str(coords.src) + " to " + str(coords.dst) + "\n")

            if self.next_player == Player.Attacker and move_type == "attack":
                file.write("Attacker attacked " + str(coords) + "\n")
            elif self.next_player == Player.Defender and move_type == "attack":
                file.write("Defender attacked " + str(coords) + "\n")

            if self.next_player == Player.Attacker and move_type == "repair":
                file.write("Attacker repaired " + str(coords) + "\n")
            elif self.next_player == Player.Defender and move_type == "repair":
                file.write("Defender repaired " + str(coords) + "\n")

            if self.next_player == Player.Attacker and move_type == "self-destruct":
                file.write("Attacker self-destruct\n")
            elif self.next_player == Player.Defender and move_type == "self-destruct":
                file.write("Defender self-destruct\n")

    def perform_move(self, coords: CoordPair) -> Tuple[bool, str]:
        """Validate and perform a move expressed as a CoordPair."""
        is_valid, move_type, error = self.is_valid_move(coords)
        if is_valid:
            if move_type == "valid move":
                self.log_move(move_type, coords)
                self.set(coords.dst, self.get(coords.src))
                self.set(coords.src, None)
                return (True, "Move initiated")
            if move_type == "attack":
                self.log_move(move_type, coords)
                self.perform_attack(coords)
                return (True, "Attack initiated")
            if move_type == "repair":
                self.log_move(move_type, coords)
                self.perform_repair(coords)
                return (True, "Repair initiated")
            if move_type == "self-destruct":
                self.log_move(move_type, coords)
                self.perform_self_destruction(coords)
                return (True, "Self-destruction initiated")

        else:
            if error is not None:
                print(error)
            return (False, "Invalid move")

    """ No logging of game states"""
    def ai_move(self, coords: CoordPair) -> Tuple[bool, str]:
        """Validate and perform a move expressed as a CoordPair."""
        is_valid, move_type, error = self.is_valid_move(coords)
        if is_valid:
            if move_type == "valid move":
                self.set(coords.dst, self.get(coords.src))
                self.set(coords.src, None)
                return (True, "Move initiated")
            if move_type == "attack":
                self.perform_attack(coords)
                return (True, "Attack initiated")
            if move_type == "repair":
                self.perform_repair(coords)
                return (True, "Repair initiated")
            if move_type == "self-destruct":
                self.perform_self_destruction(coords)
                return (True, "Self-destruction initiated")

        print(error)
        return (False, "Invalid move")

    def next_turn(self):
        """Transitions game to the next turn."""
        self.next_player = self.next_player.next()
        self.turns_played += 1

    def to_string(self) -> str:
        """Pretty text representation of the game."""
        dim = self.options.dim
        output = ""
        output += f"Next player: {self.next_player.name}\n"
        output += f"Turns played: {self.turns_played}\n"
        coord = Coord()
        output += "\n   "
        for col in range(dim):
            coord.col = col
            label = coord.col_string()
            output += f"{label:^3} "
        output += "\n"
        for row in range(dim):
            coord.row = row
            label = coord.row_string()
            output += f"{label}: "
            for col in range(dim):
                coord.col = col
                unit = self.get(coord)
                if unit is None:
                    output += " .  "
                else:
                    output += f"{str(unit):^3} "
            output += "\n"
        with open("gameTrace-<" + str(self.options.alpha_beta) + ">-<" + str(self.options.max_time) + ">-<" + str(
                self.options.max_turns) + ">.txt", "a", encoding="utf-8") as file:
            file.write(f"Board:\n  {output}")

        return output

    """ Branching factor is total number of children divided by total number of parents in the tree"""
    def determine_branching_factor(self):
        try:
            branching_factor = (len(tree.nodes)-1) / PARENT
        except ZeroDivisionError:
            branching_factor = 0
        return branching_factor

    def __str__(self) -> str:
        """Default string representation of a game."""
        return self.to_string()

    def is_valid_coord(self, coord: Coord) -> bool:
        """Check if a Coord is valid within out board dimensions."""
        dim = self.options.dim
        if coord.row < 0 or coord.row >= dim or coord.col < 0 or coord.col >= dim:
            return False
        return True

    def read_move(self) -> CoordPair:
        """Read a move from keyboard and return as a CoordPair."""
        while True:
            s = input(F'Player {self.next_player.name}, enter your move: ')
            coords = CoordPair.from_string(s)
            if coords is not None and self.is_valid_coord(coords.src) and self.is_valid_coord(coords.dst):
                return coords
            else:
                print('Invalid coordinates! Try again.')

    def human_turn(self):
        global current_node_id
        """Human player plays a move (or get via broker)."""
        global current_node_id
        if self.options.broker is not None:
            print("Getting next move with auto-retry from game broker...")
            while True:
                mv = self.get_move_from_broker()
                if mv is not None:
                    (success, result) = self.perform_move(mv)
                    print(f"Broker {self.next_player.name}: ", end='')
                    print(result)
                    if success:
                        self.next_turn()
                        break
                sleep(0.1)
        else:
            while True:
                mv = self.read_move()
                if mv is not None:
                    (success, result) = self.perform_move(mv)
                    if success:
                        print(f"Player {self.next_player.name}: ", end='')
                        print(result)
                        self.next_turn()

                    if not success:
                        print("The move is not valid! Try again.")

                    # If human is playing against AI, update the current_node of tree
                    if (
                            self.options.game_type == GameType.AttackerVsComp and current_node_id > 0) or self.options.game_type == GameType.CompVsDefender:
                        for child in tree.nodes[current_node_id].children:
                            if child.game == self:
                                current_node_id = child.id
                                break
                    break

    def computer_turn(self) -> CoordPair | None:
        """Computer plays a move."""
        mv = self.suggest_move()
        if mv is not None:
            (success, result) = self.perform_move(mv)
            if success:
                print(f"Tree Size: {len(tree.nodes)}")
                print(f"Branching Factor: {self.determine_branching_factor():1f}")
                print(f"\nNumber of games states for this move: \n", end='')
                for key, value in depth_counts.items():
                    print(f"Depth {key} {value}")
                print(f"\nComputer {self.next_player.name}: ", end='')
                print(result)
                with open(
                        "gameTrace-<" + str(self.options.alpha_beta) + ">-<" + str(self.options.max_time) + ">-<" + str(
                                self.options.max_turns) + ">.txt", "a", encoding="utf-8") as file:
                    file.write(f"\nBranching Factor: {self.determine_branching_factor()}\n")
                self.next_turn()
        return mv

    def player_units(self, player: Player) -> Iterable[Tuple[Coord, Unit]]:
        """Iterates over all units belonging to a player."""
        for coord in CoordPair.from_dim(self.options.dim).iter_rectangle():
            unit = self.get(coord)
            if unit is not None and unit.player == player:
                yield (coord, unit)

    def is_finished(self) -> bool:
        """Check if the game is over."""
        return self.has_winner() is not None

    def has_winner(self) -> Player | None:
        """Check if the game is over and returns winner"""
        if self.options.max_turns is not None and self.turns_played >= self.options.max_turns:
            return Player.Defender
        if self._attacker_has_ai:
            if self._defender_has_ai:
                return None
            else:
                return Player.Attacker
        return Player.Defender

    def move_candidates(self) -> Iterable[CoordPair]:
        """Generate valid move candidates for the next player."""
        move = CoordPair()
        for (src, _) in self.player_units(self.next_player):
            move.src = src
            for dst in src.iter_adjacent():
                move.dst = dst
                if self.is_valid_move(move):
                    yield move.clone()
            move.dst = src
            yield move.clone()

    def random_move(self) -> Tuple[int, CoordPair | None, float]:
        """Returns a random move."""
        move_candidates = list(self.move_candidates())
        random.shuffle(move_candidates)
        if len(move_candidates) > 0:
            return (0, move_candidates[0], 1)
        else:
            return (0, None, 0)


    """Suggest the next move using minimax alpha beta"""
    def suggest_move(self) -> CoordPair | None:
        global current_node_id, start_time, time_limit_exceeded, depth_counts, last_algo_time, time_ratio, time_elapsed_last_move

        depth_counts = defaultdict(default_inner_dict)
        start_time = datetime.now()
        time_limit_exceeded = False

        # dynamically allocated time for a turn based on max_time
        # this can be changed according to max_time that user will want to use,
        # if you have issues, just comment them out and set them to 50
        """ Adjust these to your own computer capacity """
        avg_ratio = 0.25
        lowest_ratio = 0.20
        highest_ratio = 0.85
        if last_algo_time == 0:
            if self.options.max_depth > 6:
                time_ratio = avg_ratio
            else:
                time_ratio = avg_ratio + 0.1
        elif not self.options.alpha_beta and self.turns_played > 15:
            time_ratio = avg_ratio

        elif last_algo_time > self.options.max_time - (time_ratio * self.options.max_time) - 0.5 \
                or self.options.max_time - time_elapsed_last_move < 0.2 * self.options.max_time:
            time_ratio = max(lowest_ratio, time_ratio - 0.40)
        elif time_elapsed_last_move < self.options.max_time - 1:
            time_ratio = min(highest_ratio, time_ratio + 0.01)

        # generating game states
        self.generate_game_tree_bfs(self.options.max_depth, parent_id=current_node_id)
        current_node = tree.nodes[current_node_id]

        # if we are only doing minimax
        if not self.options.alpha_beta:
            algo_start_time = datetime.now()
            result, node = tree.minimax(current_node)
            last_algo_time = (datetime.now() - algo_start_time).total_seconds()
            score = node.e1
            move = node.move
            current_node_id = node.id

        if self.options.alpha_beta:
            algo_start_time = datetime.now()
            tree.traverse_ordered(current_node)  # optimal ordering
            result, node = tree.alpha_beta_pruning(current_node)  # alpha beta pruning
            last_algo_time = (datetime.now() - algo_start_time).total_seconds()
            score = node.e2
            move = node.move
            current_node_id = node.id

        tree.print_tree_to_file("tree_depth.txt", current_node)
        tree.print_tree_to_file_alphabeta("tree-alpha.txt", current_node)

        elapsed_seconds = (datetime.now() - start_time).total_seconds()
        time_elapsed_last_move = elapsed_seconds
        self.stats.total_seconds += elapsed_seconds

        elapsed_seconds = (datetime.now() - start_time).total_seconds()
        self.stats.total_seconds += elapsed_seconds
        with open("gameTrace-<" + str(self.options.alpha_beta) + ">-<" + str(self.options.max_time) + ">-<" + str(
                self.options.max_turns) + ">.txt", "a", encoding="utf-8") as file:
            file.write(f"\nbranching factor {self.determine_branching_factor()}\n")
            file.write(f"Heuristic score:  {score:0.2f}\n")
            file.write(f"Heuristic used: {'e2' if self.options.alpha_beta else 'e1'}\n")
            file.write(f"Cumulative total evals: {tree.total_evals}\n")
            file.write(f"Evals per depth: ")
            for k in sorted(tree.stats.keys()):
                file.write(f"{k}:{tree.stats[k]} ")
            file.write(f"\n")
            for k in sorted(tree.stats.keys()):
                file.write(f"{k}:{int((tree.stats[k] * 100) / tree.total_evals)}% ")
            if self.stats.total_seconds > 0:
                file.write(f"\nEval perf.: {tree.total_evals / self.stats.total_seconds / 1000:0.1f}k/s")
            file.write(f"\nElapsed time: {elapsed_seconds:0.1f}s")

        print(f"Heuristic score: {score:0.2f}")
        print(f"Heuristic used: {'e2' if self.options.alpha_beta else 'e1'}") # change to e0 if used
        print(f"Elapsed time: {elapsed_seconds:0.1f}s\n")
        if elapsed_seconds > self.options.max_time:
            print("AI took too long to make a move")
            print(time_ratio)
            return

        print(f"Cumulative total evals: {tree.total_evals}")
        print(f"Evals per depth: ", end='')
        for k in sorted(tree.stats.keys()):
            print(f"{k}:{tree.stats[k]} ", end='')
        print()
        for k in sorted(tree.stats.keys()):
            print(f"{k}:{int((tree.stats[k] * 100) / tree.total_evals)}% ", end='')
        print()

        if self.stats.total_seconds > 0:
            print(f"Eval perf.: {tree.total_evals / self.stats.total_seconds / 1000:0.1f}k/s")

        return move

    """Check if generating game states is taking too much time"""
    def check_time_limit(self):
        global time_limit_exceeded, time_ratio
        current_time = datetime.now()
        elapsed_time = (current_time - start_time).total_seconds()
        if elapsed_time > time_ratio * self.options.max_time:
            time_limit_exceeded = True

    """Initializes the game tree by adding the root node"""
    def initialize_game_tree(self):
        global ID
        tree.add_node(ID, game=self, parent=None)  # starting by a max
        ID += 1

    """Iterates over the board's dimensions until unit of the player is found"""
    def generate_game_states(self, parent=None):
        self.check_time_limit()
        if time_limit_exceeded:
            return

        for coord, _ in self.player_units(self.next_player):
            self.generate_unit_moves(coord, parent)

    """Generate possible moves for the given unit at the given coordinate"""
    def generate_unit_moves(self, coord: Coord, parent=None):
        x, y = coord.row, coord.col
        global ID
        inCombat = False
        count = 0

        directions = [(0, -1), (-1, 0), (1, 0), (0, 1)]  # Up, Left, Right, Down, Self-destruct

        self.check_time_limit()
        if time_limit_exceeded:
            return

        for dx, dy in directions:
            new_x, new_y = x + dx, y + dy
            new_coord = Coord(new_x, new_y)
            next_move = CoordPair(coord, new_coord)
            result, _, invalidMove = tree.nodes[parent].game.is_valid_move(next_move)
            if invalidMove == "Sorry, this player is engaged in combat.":
                unit = self.get(Coord(new_x, new_y))
                if unit is not None and unit.player != self.next_player:
                    count += 1
                inCombat = True

            # if move is valid, perform move
            if result:
                new_board = tree.nodes[parent].game.clone()
                new_board.ai_move(next_move)
                new_board.next_turn()
                e1 = None

                if self.options.alpha_beta:
                    e1 = new_board.heuristic_1()

                # adds new game state as a node in tree
                tree.add_node(ID, game=new_board, move=next_move, e1=e1, parent=parent)
                ID += 1

        if inCombat:
            unit = self.get(Coord(x, y))
            if unit.health < 3 or count > 1:
                # self-destruct is only explored if unit is in combat
                # and already has low health or is surrounded by enemy players
                next_move = CoordPair(coord, coord)
                new_board = tree.nodes[parent].game.clone()
                new_board.ai_move(next_move)
                new_board.next_turn()
                e1 = None

                if self.options.alpha_beta:
                    e1 = new_board.heuristic_1()

                # adds new game state as a node in tree
                tree.add_node(ID, game=new_board, move=next_move, e1=e1, parent=parent)
                ID += 1

    """ Generates tree of moves for each level """
    def generate_game_tree_bfs(self, max_depth, parent_id=0):
        global PARENT, time_limit_exceeded, depth_counts

        exited_early = False

        # Initialization
        if parent_id == 0:
            self.initialize_game_tree()

        # using a queue to generate children by level
        queue = deque([(parent_id, max_depth - 1)])  # (node_id, depth)
        depth_counts[1] = {"count": 1, "is_full": False}

        while queue:
            current_id, depth = queue.popleft()

            # check if we have time left
            self.check_time_limit()
            if time_limit_exceeded:
                exited_early = True
                break

            current_children_count = len(tree.nodes[current_id].children)

            # Only generate game states if it's a leaf node
            if len(tree.nodes[current_id].children) == 0:
                PARENT += 1
                tree.nodes[current_id].game.generate_game_states(parent=current_id)
                # update children generated
                new_children_count = len(tree.nodes[current_id].children) - current_children_count
            else:
                new_children_count = len(tree.nodes[current_id].children)

            current_depth = max_depth - depth + 1

            # moving to next depth
            if current_depth not in depth_counts:
                depth_counts[current_depth - 1]["is_full"] = True

            # used for
            depth_counts[current_depth]["count"] += new_children_count

            if depth > 1:
                for child in tree.nodes[current_id].children:
                    queue.append((child.id, depth - 1))

        if not exited_early:
            depth_counts[current_depth]["is_full"] = True

    """ e0 given by instructions """
    def heuristic_0(self):
        attacker_score = 0
        defender_score = 0

        for coord, unit in self.player_units(Player.Attacker):
            if unit.type == UnitType.Virus:
                attacker_score += 3
            elif unit.type == UnitType.Tech:
                attacker_score += 3
            elif unit.type == UnitType.Firewall:
                attacker_score += 3
            elif unit.type == UnitType.Program:
                attacker_score += 3
            elif unit.type == UnitType.AI:
                attacker_score += 9999

        for coord, unit in self.player_units(Player.Defender):
            if unit.type == UnitType.Virus:
                defender_score += 3
            elif unit.type == UnitType.Tech:
                defender_score += 3
            elif unit.type == UnitType.Firewall:
                defender_score += 3
            elif unit.type == UnitType.Program:
                defender_score += 3
            elif unit.type == UnitType.AI:
                defender_score += 9999

        return attacker_score - defender_score

    """ e1, trivial heuristic, checking the number of units, assigning weight and health weight"""
    def heuristic_1(
            self) -> int:  # directions = [(0, -1), (-1, 0), (1, 0), (0, 1), (0, 0)]  # Up, Left, Right, Down, Self-destruct

        attacker_score = 0
        defender_score = 0

        for coord, unit in self.player_units(Player.Attacker):
            if unit.type == UnitType.Virus:
                attacker_score += 20
                attacker_score += unit.health * 2
            elif unit.type == UnitType.Tech:
                attacker_score += 20
                attacker_score += unit.health * 2
            elif unit.type == UnitType.Firewall:
                attacker_score += 15
                attacker_score += unit.health * 1.5
            elif unit.type == UnitType.Program:
                attacker_score += 10
                attacker_score += unit.health * 1
            elif unit.type == UnitType.AI:
                attacker_score += 9999

        for coord, unit in self.player_units(Player.Defender):
            if unit.type == UnitType.Virus:
                defender_score += 20
                defender_score += unit.health * 2
            elif unit.type == UnitType.Tech:
                defender_score += 20
                defender_score += unit.health * 2
            elif unit.type == UnitType.Firewall:
                defender_score += 15
                defender_score += unit.health * 1.5
            elif unit.type == UnitType.Program:
                defender_score += 10
                defender_score += unit.health * 1
            elif unit.type == UnitType.AI:
                defender_score += 9999

        return attacker_score - defender_score

    """ e2, more complex e, that adds health and weight """
    def heuristic_2(self) -> int:
        attacker_score = 0
        defender_score = 0

        # Locate the positions of both AIs
        attacker_ai_coord = None
        defender_ai_coord = None

        # Loop through the board only once
        for y in range(self.options.dim):
            for x in range(self.options.dim):
                unit = self.get(Coord(x, y))
                coord = Coord(x, y)

                if unit:
                    if unit.type == UnitType.AI:
                        if unit.player == Player.Attacker:
                            attacker_ai_coord = coord
                        else:
                            defender_ai_coord = coord

                    # Other scoring based on the player and unit type
                    if unit.player == Player.Attacker:
                        attacker_score += random.randrange(30)  # to escape constant games
                        if unit.type == UnitType.Virus:
                            attacker_score += 20 + unit.health * 2
                            # the closer the virus to AI, the better
                            if defender_ai_coord:
                                distance_to_opponent_ai = coord.euclidean_distance_to(defender_ai_coord)
                                attacker_score += 100 / (distance_to_opponent_ai + 1)
                        elif unit.type == UnitType.Tech:
                            attacker_score += 20 + unit.health * 2
                        elif unit.type == UnitType.Firewall:
                            attacker_score += 15 + unit.health * 1.5
                        elif unit.type == UnitType.Program:
                            attacker_score += 10 + unit.health
                        elif unit.type == UnitType.AI:
                            attacker_score += 9999

                    elif unit.player == Player.Defender:
                        defender_score += random.randrange(30)
                        if unit.type == UnitType.Virus:
                            defender_score += 20 + unit.health * 2
                        elif unit.type == UnitType.Tech:
                            defender_score += 20 + unit.health * 2
                        elif unit.type == UnitType.Firewall:
                            defender_score += 15 + unit.health * 1.5
                        elif unit.type == UnitType.Program:
                            defender_score += 10 + unit.health
                        elif unit.type == UnitType.AI:
                            defender_score += 9999

                    # mobility aspect added, if it can more, its better
                    for adj_coord in coord.iter_all8_adjacent():
                        if self.is_valid_coord(adj_coord) and self.is_valid_move(CoordPair(coord, adj_coord)):
                            if unit.player == Player.Attacker:
                                attacker_score += 2
                            else:
                                defender_score += 2

        # Defense bonus if own AI is close to an opponent's Virus
        if defender_ai_coord:
            for opp_coord, opp_unit in self.player_units(Player.Attacker):
                if opp_unit.type == UnitType.Virus:
                    distance_to_virus = defender_ai_coord.euclidean_distance_to(opp_coord)
                    defender_score -= 100 / (distance_to_virus + 1)  # Negative score for potential threat

        return attacker_score - defender_score

    def post_move_to_broker(self, move: CoordPair):
        """Send a move to the game broker."""
        if self.options.broker is None:
            return
        data = {
            "from": {"row": move.src.row, "col": move.src.col},
            "to": {"row": move.dst.row, "col": move.dst.col},
            "turn": self.turns_played
        }
        try:
            r = requests.post(self.options.broker, json=data)
            if r.status_code == 200 and r.json()['success'] and r.json()['data'] == data:
                # print(f"Sent move to broker: {move}")
                pass
            else:
                print(f"Broker error: status code: {r.status_code}, response: {r.json()}")
        except Exception as error:
            print(f"Broker error: {error}")

    def get_move_from_broker(self) -> CoordPair | None:
        """Get a move from the game broker."""
        if self.options.broker is None:
            return None
        headers = {'Accept': 'application/json'}
        try:
            r = requests.get(self.options.broker, headers=headers)
            if r.status_code == 200 and r.json()['success']:
                data = r.json()['data']
                if data is not None:
                    if data['turn'] == self.turns_played + 1:
                        move = CoordPair(
                            Coord(data['from']['row'], data['from']['col']),
                            Coord(data['to']['row'], data['to']['col'])
                        )
                        print(f"Got move from broker: {move}")
                        return move
                    else:
                        # print("Got broker data for wrong turn.")
                        # print(f"Wanted {self.turns_played+1}, got {data['turn']}")
                        pass
                else:
                    # print("Got no data from broker")
                    pass
            else:
                print(f"Broker error: status code: {r.status_code}, response: {r.json()}")
        except Exception as error:
            print(f"Broker error: {error}")
        return None


##############################################################################################################
def default_inner_dict():
    return {"count": 0, "is_full": False}


# create a new global tree
tree = Tree()

# dict of levels per move
depth_counts = defaultdict(default_inner_dict)


def main():
    # parse command line arguments
    parser = argparse.ArgumentParser(
        prog='ai_wargame',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--max_depth', type=int, help='maximum search depth')
    parser.add_argument('--max_time', type=float, help='maximum search time')
    parser.add_argument('--game_type', type=str, default="manual", help='game type: auto|attacker|defender|manual')
    parser.add_argument('--broker', type=str, help='play via a game broker')
    parser.add_argument('--max_turns', type=int, help='max number of turns the game will go on for')
    parser.add_argument('--alpha_beta', type=str, help='force the use of alpha-beta pruning')

    args = parser.parse_args()

    # parse the game type
    if args.game_type == "attacker":
        game_type = GameType.AttackerVsComp
    elif args.game_type == "defender":
        game_type = GameType.CompVsDefender
    elif args.game_type == "manual":
        game_type = GameType.AttackerVsDefender
    else:
        game_type = GameType.CompVsComp

    # set up game options
    options = Options(game_type=game_type)

    # override class defaults via command line options
    if args.max_depth is not None:
        options.max_depth = args.max_depth
    if args.max_time is not None:
        options.max_time = args.max_time
    if args.broker is not None:
        options.broker = args.broker
    if args.max_turns is not None:
        options.max_turns = args.max_turns
    if args.alpha_beta is not None:
        if args.alpha_beta == 'true':
            options.alpha_beta = True
        else:
            options.alpha_beta = False

    with open("gameTrace-<" + str(options.alpha_beta) + ">-<" + str(options.max_time) + ">-<" + str(
            options.max_turns) + ">.txt", "w", encoding="utf-8") as file:
        file.write("Game Paramaters:\n" + str(options) + "\n")

    # create a new game
    game = Game(options=options)

    # the main game loop
    while True:
        print()
        print(game)
        # with open("gameTrace-<" + str(options.alpha_beta) + ">-<" + str(options.max_time) + ">-<" + str(
        #     options.max_turns) + ">.txt", "a", encoding="utf-8") as file:
        #     file.write(game.to_string())
        winner = game.has_winner()
        if winner is not None:
            with open("gameTrace-<" + str(options.alpha_beta) + ">-<" + str(options.max_time) + ">-<" + str(
                    options.max_turns) + ">.txt", "a", encoding="utf-8") as file:
                file.write(f"{winner.name} wins! {winner.name} won in {game.turns_played} moves.\n")

            print(f"{winner.name} wins! {winner.name} won in {game.turns_played} moves.")
            break
        if game.turns_played == options.max_turns:
            print(
                f"Maximum of moves reached. {Player.Defender.name} wins! {Player.Defender.name} won in {game.turns_played} moves.")
            file.write(
                f"Maximum of moves reached. {Player.Defender.name} wins! {Player.Defender.name} won in {game.turns_played} moves.\n")
            exit(1)
        if game.options.game_type == GameType.AttackerVsDefender:
            game.human_turn()
        elif game.options.game_type == GameType.AttackerVsComp and game.next_player == Player.Attacker:
            game.human_turn()
        elif game.options.game_type == GameType.CompVsDefender and game.next_player == Player.Defender:
            game.human_turn()
        else:
            player = game.next_player
            move = game.computer_turn()
            if move is not None:
                game.post_move_to_broker(move)
            else:
                print("Computer doesn't know what to do!!!")
                if game.next_player is Player.Attacker:
                    game._attacker_has_ai = False
                else:
                    game._defender_has_ai = False


##############################################################################################################

if __name__ == '__main__':
    main()
