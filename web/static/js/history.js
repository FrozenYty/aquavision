// Immutable pre-edit snapshots. A gesture records once; cancelling discards that snapshot.
export function rememberEdit(history, objects, selected) {
  return [...history, structuredClone({ objects, selected })];
}

export function undoEdit(history) {
  if (!history.length) return null;
  return { ...structuredClone(history.at(-1)), history: history.slice(0, -1) };
}
