// The one species list every screen shares (glossary §4, class-code order). Import it here and
// nowhere else: the chart legends, the box labels and the review counters must never drift apart,
// and a second copy is exactly how they did before (PR #42 review, item 6).

export const SPECIES = {
  holothurian: "海参",
  strongylocentrotus: "海胆",
  chlamys: "扇贝",
  asterias: "海星",
};
