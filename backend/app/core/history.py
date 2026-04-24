from dataclasses import dataclass, field

import numpy as np


@dataclass
class HistoryManager:
    undo_stack: list[np.ndarray] = field(default_factory=list)
    redo_stack: list[np.ndarray] = field(default_factory=list)

    def push(self, snapshot: np.ndarray) -> None:
        self.undo_stack.append(snapshot.copy())
        self.redo_stack.clear()

    def undo(self, current: np.ndarray) -> np.ndarray:
        if not self.undo_stack:
            raise ValueError("Undo history is empty.")
        self.redo_stack.append(current.copy())
        return self.undo_stack.pop()

    def redo(self, current: np.ndarray) -> np.ndarray:
        if not self.redo_stack:
            raise ValueError("Redo history is empty.")
        self.undo_stack.append(current.copy())
        return self.redo_stack.pop()

    @property
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self.redo_stack)
