import numpy as np

from logger import logger
from tableturf.model.grid import Grid


class Pattern:
    def __init__(self, grid: np.ndarray):
        """
        :param grid: Pattern.
        """
        if isinstance(grid[0][0], Grid):
            grid = np.vectorize(lambda x: x.value)(grid)
        inks = grid != Grid.Empty.value
        row_mask = np.any(inks, axis=1)
        col_mask = np.any(inks, axis=0)
        self.__grid = grid[row_mask][:, col_mask].copy()
        if np.minimum(*self.__grid.shape) > 8:
            logger.warn(f"Pattern width/height > 8. grid={self.__grid}")
        self.__grid.setflags(write=False)

        indexes = np.argwhere((self.__grid == Grid.MyInk.value) | (self.__grid == Grid.MySpecial.value))
        self.__squares = self.__grid[indexes[:, 0], indexes[:, 1]]
        self.__offsets = indexes - indexes[0][np.newaxis, ...]
        self.__size, _ = indexes.shape

    @property
    def size(self) -> int:
        """
        The number of squares the pattern covers.
        """
        return self.__size

    @property
    def offset(self) -> np.ndarray:
        """
        All square offsets of the pattern. The top-left square is the origin point.
        """
        return self.__offsets

    @property
    def squares(self) -> np.ndarray:
        """
        All squares from left to right, then from up to down.
        """
        return self.__squares

    @property
    def grid(self) -> np.ndarray:
        """
        Trimmed grid.
        """
        return self.__grid

    def rotate(self, rotate):
        return Pattern(np.rot90(self.__grid, rotate))

    def __hash__(self):
        return hash(str(self.__offsets))

    def __eq__(self, other):
        if isinstance(other, Pattern):
            return np.all(self.__offsets == other.__offsets) and np.all(self.__squares == other.__squares)
        return NotImplemented

    def __repr__(self):
        return str(self.__grid)

    def __str__(self):
        return repr(self)


class Card:
    # counterclockwise 90°
    __ROTATION_MATRIX = np.array([
        [0, -1],
        [1, 0],
    ])
    __INVERSE_ROTATION_MATRIX = np.linalg.inv(__ROTATION_MATRIX).astype(np.int)

    def __init__(self, grid: np.ndarray, sp_cost: int):
        """
        Represent a card. Each inked square is assigned an ID, which numbers first from left to right, then from up to down.

        :param grid: Card pattern.
        :param sp_cost: Special Points that a Special Attack costs.
        """
        self.__sp_cost = sp_cost
        self.__patterns = [Pattern(np.rot90(grid, i)) for i in range(4)]
        self.__size = self.__patterns[0].size

    @property
    def size(self) -> int:
        """
        The number of squares the pattern covers.
        """
        return self.__size

    @property
    def sp_cost(self) -> int:
        """
        Special Points that a Special Attack costs.
        """
        return self.__sp_cost

    def get_pattern(self, rotate: int = 0) -> Pattern:
        """
        Get the pattern of the card.

        :param rotate: The times of rotation (counterclockwise 90°)
        """
        return self.__patterns[rotate % 4]

    def __hash__(self):
        return hash(self.__patterns[0])

    def __eq__(self, other):
        if isinstance(other, Card):
            return np.all(self.__patterns[0] == other.__patterns[0])
        return False

    def __repr__(self):
        return f'Card(pattern={self.__patterns[0]}, sp_cost={self.__sp_cost})'

    def __str__(self):
        return repr(self)
