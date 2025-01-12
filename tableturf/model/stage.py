import numpy as np

from tableturf.model.grid import Grid


class Stage:
    __NEIGHBOURHOOD_OFFSETS = np.array([
        [-1, -1],
        [-1, 0],
        [-1, 1],
        [0, -1],
        [0, 1],
        [1, -1],
        [1, 0],
        [1, 1]
    ])

    def __init__(self, grid: np.ndarray):
        """
        Represent a stage.

        :param grid: Stage pattern.
        """
        if isinstance(grid[0][0], Grid):
            self.__grid = np.vectorize(lambda x: x.value)(grid)
        else:
            self.__grid = grid.copy()
        self.__size = np.count_nonzero(self.grid != Grid.Wall.value)

        def neighborhoods(idx: np.ndarray) -> np.ndarray:
            return Stage.__NEIGHBOURHOOD_OFFSETS + idx

        def within_grid(indexes: np.ndarray) -> np.ndarray:
            m, n = self.shape
            xs = indexes[:, 0]
            ys = indexes[:, 1]
            return indexes[(xs >= 0) & (xs < m) & (ys >= 0) & (ys < n)]

        def is_fiery(idx: np.ndarray) -> bool:
            nbhd = neighborhoods(idx)
            valid_nbhd = within_grid(nbhd)
            return np.all(self.__grid[valid_nbhd[:, 0], valid_nbhd[:, 1]] != Grid.Empty.value)

        def split_sp(sp: np.ndarray) -> tuple:
            if sp.size == 0:
                return np.zeros((0, 2), dtype=int), np.zeros((0, 2), dtype=int)
            is_sp_fiery = np.array([is_fiery(idx) for idx in sp])
            return sp[is_sp_fiery], sp[np.bitwise_not(is_sp_fiery)]

        def ink_neighborhoods(idx: np.ndarray) -> np.ndarray:
            nbhd = within_grid(Stage.__NEIGHBOURHOOD_OFFSETS + idx)
            valid_nbhd = nbhd[self.__grid[nbhd[:, 0], nbhd[:, 1]] == Grid.Empty.value]
            invalid = np.full(shape=(8 - valid_nbhd.shape[0], 2), fill_value=-1)
            return np.concatenate((valid_nbhd, invalid), axis=0)

        def collect_ink_neighborhoods(ink: np.ndarray) -> np.ndarray:
            return within_grid(np.unique(np.array([ink_neighborhoods(idx) for idx in ink]).reshape(-1, 2), axis=0))

        def sp_neighborhoods(idx: np.ndarray) -> np.ndarray:
            nbhd = within_grid(Stage.__NEIGHBOURHOOD_OFFSETS + idx)
            values = self.__grid[nbhd[:, 0], nbhd[:, 1]]
            valid_nbhd = nbhd[(values == Grid.Empty.value) | (values == Grid.MyInk.value) | (values == Grid.HisInk.value)]
            invalid = np.full(shape=(8 - valid_nbhd.shape[0], 2), fill_value=-1)
            return np.concatenate((valid_nbhd, invalid), axis=0)

        def collect_sp_neighborhoods(sp: np.ndarray) -> np.ndarray:
            return within_grid(np.unique(np.array([sp_neighborhoods(idx) for idx in sp]).reshape(-1, 2), axis=0))

        self.__my_ink = np.argwhere((self.__grid == Grid.MyInk.value) | (self.__grid == Grid.MySpecial.value))
        self.__my_sp = np.argwhere(self.__grid == Grid.MySpecial.value)
        self.__my_fiery_sp, self.__my_unfiery_sp = split_sp(self.__my_sp)
        self.__my_neighborhoods = collect_ink_neighborhoods(self.__my_ink)
        self.__my_sp_neighborhoods = collect_sp_neighborhoods(self.__my_sp)

        self.__his_ink = np.argwhere((self.__grid == Grid.HisInk.value) | (self.__grid == Grid.HisSpecial.value))
        self.__his_sp = np.argwhere(self.__grid == Grid.HisSpecial.value)
        self.__his_fiery_sp, self.__his_unfiery_sp = split_sp(self.__his_sp)
        self.__his_neighborhoods = collect_ink_neighborhoods(self.__his_ink)
        self.__his_sp_neighborhoods = collect_sp_neighborhoods(self.__his_sp)

        self.__fiery_grid = np.zeros_like(self.__grid, dtype=bool)
        self.__fiery_grid[self.__my_fiery_sp[:, 0], self.__my_fiery_sp[:, 1]] = True
        self.__fiery_grid[self.__his_fiery_sp[:, 0], self.__his_fiery_sp[:, 1]] = True

        self.__grid.setflags(write=False)
        self.__fiery_grid.setflags(write=False)
        self.__my_ink.setflags(write=False)
        self.__my_sp.setflags(write=False)
        self.__my_fiery_sp.setflags(write=False)
        self.__my_neighborhoods.setflags(write=False)
        self.__my_sp_neighborhoods.setflags(write=False)
        self.__his_ink.setflags(write=False)
        self.__his_sp.setflags(write=False)
        self.__his_fiery_sp.setflags(write=False)
        self.__his_neighborhoods.setflags(write=False)
        self.__his_sp_neighborhoods.setflags(write=False)

    @property
    def grid(self) -> np.ndarray:
        """
        Pattern of the Stage. (h w)
        """
        return self.__grid

    @property
    def fiery_grid(self) -> np.ndarray:
        """
        Indicate which square is fiery. (h w)
        """
        return self.__fiery_grid

    @property
    def shape(self) -> tuple:
        """
        A tuple. Height and width of the stage.
        """
        return self.__grid.shape

    @property
    def size(self) -> int:
        """
        The number of empty square that the stage contains.
        """
        return self.__size

    @property
    def my_sp(self) -> np.ndarray:
        """
        Indexes of my Special Space on the stage. shape = (N, 2)
        """
        return self.__my_sp

    @property
    def my_ink(self) -> np.ndarray:
        """
        Indexes of my ink on the stage. shape = (N, 2)
        """
        return self.__my_ink

    @property
    def my_fiery_sp(self) -> np.ndarray:
        """
        Indexes of my fiery Special Space on the stage. shape = (N, 2)
        """
        return self.__my_fiery_sp

    @property
    def my_unfiery_sp(self) -> np.ndarray:
        """
        Indexes of my un-fiery Special Space on the stage. shape = (N, 2)
        """
        return self.__my_unfiery_sp

    @property
    def my_neighborhoods(self) -> np.ndarray:
        """
        Indexes of the empty squares nearby my ink on the stage. shape = (N, 2)
        """
        return self.__my_neighborhoods

    @property
    def my_sp_neighborhoods(self) -> np.ndarray:
        """
        Indexes of the squares nearby my Special Space on the stage. The squares are Empty, MyInk or HisInk. shape = (N, 2)
        """
        return self.__my_sp_neighborhoods

    @property
    def his_sp(self) -> np.ndarray:
        """
        Indexes of opponent's Special Space on the stage. shape = (N, 2)
        """
        return self.__his_sp

    @property
    def his_ink(self) -> np.ndarray:
        """
        Indexes of opponent's ink on the stage. shape = (N, 2)
        """
        return self.__his_ink

    @property
    def his_fiery_sp(self) -> np.ndarray:
        """
        Indexes of opponent's fiery Special Space on the stage. shape = (N, 2)
        """
        return self.__his_fiery_sp

    @property
    def his_unfiery_sp(self) -> np.ndarray:
        """
        Indexes of opponent's un-fiery Special Space on the stage. shape = (N, 2)
        """
        return self.__his_unfiery_sp

    @property
    def his_neighborhoods(self) -> np.ndarray:
        """
        Indexes of the empty squares nearby opponent's ink on the stage. shape = (N, 2)
        """
        return self.__his_neighborhoods

    @property
    def his_sp_neighborhoods(self) -> np.ndarray:
        """
        Indexes of the squares nearby opponent's Special Space on the stage. The squares are Empty, MyInk or HisInk. shape = (N, 2)
        """
        return self.__his_sp_neighborhoods

    def __repr__(self):
        return f'Stage(grid={self.__grid})'

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        if isinstance(other, Stage):
            return np.all(self.__grid == other.__grid)
        return False
