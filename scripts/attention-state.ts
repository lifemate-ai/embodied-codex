/**
 * Attention state — derives a compact attention-control summary from current desire state.
 *
 * This is intentionally not a sentiment label. It describes where attention is likely
 * to be pulled under the current continuous-control regime.
 */

import { formatAttentionSummary, loadDesireState } from "./attention-lib";

const payload = await loadDesireState();
console.log(formatAttentionSummary(payload));
