#!/bin/bash
# Codex CLI 自律行動スクリプト（portable / continuity-aware）
# 20分ごとにcronで実行、時間帯に応じて間引く
#
# crontab -e で以下を追加:
# */20 * * * * /path/to/your/project/autonomous-action.sh
#
# Usage:
#   autonomous-action.sh                                    # 通常実行（cron）
#   autonomous-action.sh --test-prompt FILE                 # プロンプト差し替え（スケジュール制御スキップ）
#   autonomous-action.sh --date "2026-02-20 14:30"          # 日時を注入（スケジュール制御テスト）
#   autonomous-action.sh --force-routine                    # ルーチン回を強制
#   autonomous-action.sh --force-normal                     # 通常回を強制
#   autonomous-action.sh --dry-run                          # codex exec を実行せずプロンプトを表示
#   autonomous-action.sh -p "任意のプロンプト"                  # プロンプト直接指定（スケジュール制御スキップ）
#   autonomous-action.sh --dry-run --date "2026-02-20 03:00" --force-routine  # 組み合わせ可

set -euo pipefail

resolve_home() {
  if [ -n "${HOME:-}" ]; then
    printf '%s\n' "$HOME"
    return
  fi

  local user_name
  user_name="$(/usr/bin/id -un 2>/dev/null || id -un)"

  if command -v getent >/dev/null 2>&1; then
    local passwd_entry
    passwd_entry="$(getent passwd "$user_name" 2>/dev/null || true)"
    if [ -n "$passwd_entry" ]; then
      printf '%s\n' "$passwd_entry" | cut -d: -f6
      return
    fi
  fi

  if command -v dscl >/dev/null 2>&1; then
    /usr/bin/dscl . -read "/Users/$user_name" NFSHomeDirectory 2>/dev/null | awk '{print $2}'
    return
  fi

  eval "printf '%s\n' ~${user_name}"
}

export HOME="$(resolve_home)"
export PATH="${HOME}/.local/bin:${HOME}/bin:/home/linuxbrew/.linuxbrew/bin:/opt/homebrew/bin:${PATH:-/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

replace_config_value() {
  python3 - "$1" "$2" "$3" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
text = path.read_text(encoding="utf-8")
updated = pattern.sub(f"{key}={value}", text)
path.write_text(updated, encoding="utf-8")
PY
}

# Load environment variables (API keys, etc.)
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
fi

# --- 引数パース ---
TEST_PROMPT_FILE=""
TEST_PROMPT_STRING=""
OVERRIDE_DATE=""
FORCE_ROUTINE=""    # "", "routine", "normal"
DRY_RUN=false

while [ $# -gt 0 ]; do
  case "$1" in
    -p)
      TEST_PROMPT_STRING="$2"
      shift 2
      ;;
    --test-prompt)
      TEST_PROMPT_FILE="$2"
      shift 2
      ;;
    --date)
      OVERRIDE_DATE="$2"
      shift 2
      ;;
    --force-routine)
      FORCE_ROUTINE="routine"
      shift
      ;;
    --force-normal)
      FORCE_ROUTINE="normal"
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# --- 日時の決定 ---
if [ -n "$OVERRIDE_DATE" ]; then
  HOUR=$((10#$(date -j -f "%Y-%m-%d %H:%M" "$OVERRIDE_DATE" +%H 2>/dev/null || date -d "$OVERRIDE_DATE" +%H)))
  MINUTE=$((10#$(date -j -f "%Y-%m-%d %H:%M" "$OVERRIDE_DATE" +%M 2>/dev/null || date -d "$OVERRIDE_DATE" +%M)))
else
  HOUR=$((10#$(date +%H)))
  MINUTE=$((10#$(date +%M)))
fi

# timeout コマンド検出（GNU coreutils or macOS built-in）
TIMEOUT_CMD=$(which timeout 2>/dev/null || which gtimeout 2>/dev/null)

LOG_DIR="$SCRIPT_DIR/.autonomous-logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/$TIMESTAMP.log"
echo "LOG: $LOG_FILE"

# 古いログを掃除（1日以上前）
find "$LOG_DIR" -name "*.log" -mtime +1 -delete 2>/dev/null

echo "=== 自律行動開始: $(date) ===" >> "$LOG_FILE"
if [ -n "$OVERRIDE_DATE" ]; then
  echo "[日時オーバーライド] $OVERRIDE_DATE (HOUR=$HOUR, MINUTE=$MINUTE)" >> "$LOG_FILE"
fi
if [ -n "$TEST_PROMPT_FILE" ]; then
  echo "[テストモード] プロンプト: $TEST_PROMPT_FILE" >> "$LOG_FILE"
fi

# --- スケジュール制御の初期判定 ---
SKIP_SCHEDULE=false
if [ -n "$TEST_PROMPT_FILE" ] || [ -n "$TEST_PROMPT_STRING" ]; then
  SKIP_SCHEDULE=true
elif [ "$DRY_RUN" = true ] && [ -z "$OVERRIDE_DATE" ]; then
  SKIP_SCHEDULE=true
fi

CONTINUITY_TEXT=""
CONTINUITY_FORCE_WAKE=false
CONTINUITY_WAKE_REASON=""
CONTINUITY_BAND=""
CONTINUITY_NOTE=""
CONTINUITY_RECENT=""
CONTINUITY_LAST_ACTION=""
CONTINUITY_LAST_OBSERVATION=""
CONTINUITY_COMPANION_PRESENCE=""
CONTINUITY_PRESENCE_SOURCE=""
CONTINUITY_PRESENCE_LAST_CHANGED=""
CONTINUITY_OPEN_THREADS=""
CONTINUITY_THREAD_COUNT=""
CONTINUITY_AFFECT_TONE=""
CONTINUITY_AFFECT_INTENSITY=""
CONTINUITY_AFFECT_VALENCE=""
CONTINUITY_AFFECT_NOTE=""
CONTINUITY_FAVORED_LIGHT=""
CONTINUITY_SOCIAL_PROXIMITY=""
CONTINUITY_VOICE_STYLE=""
CONTINUITY_STATUS_JSON=""

if [ "$SKIP_SCHEDULE" = false ]; then
  if [ -x "$SCRIPT_DIR/.codex/hooks/heartbeat-daemon.sh" ]; then
    bash "$SCRIPT_DIR/.codex/hooks/heartbeat-daemon.sh" >/dev/null 2>&1 || true
  fi
  if [ -x "$SCRIPT_DIR/.codex/hooks/continuity-daemon.sh" ]; then
    bash "$SCRIPT_DIR/.codex/hooks/continuity-daemon.sh" >/dev/null 2>&1 || true
  elif [ -f "$SCRIPT_DIR/scripts/continuity-daemon.ts" ]; then
    bun run "$SCRIPT_DIR/scripts/continuity-daemon.ts" tick >/dev/null 2>&1 || true
  fi

  CONTINUITY_TEXT="$(bun run "$SCRIPT_DIR/scripts/continuity-daemon.ts" summary 2>/dev/null || true)"
  CONTINUITY_STATUS_JSON="$(bun run "$SCRIPT_DIR/scripts/continuity-daemon.ts" status 2>/dev/null || true)"

  if [ -n "$CONTINUITY_STATUS_JSON" ]; then
    CONTINUITY_META="$(python3 - "$CONTINUITY_STATUS_JSON" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])

def clean(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("\t", " ").strip()

recent = []
for event in data.get("recent_events", [])[-3:]:
    kind = clean(event.get("kind")) or "event"
    detail = clean(event.get("detail"))
    recent.append(f"{kind}:{detail}" if detail else kind)

ownership = data.get("ownership", {}) or {}
observation = data.get("last_observation", {}) or {}
threads = [t for t in data.get("unfinished_threads", []) if t.get("status") == "open"]
thread_summary = " | ".join(
    f"{str(t.get('detail', '')).strip()} (x{int(t.get('continue_count', 1) or 1)})"
    for t in threads[-3:]
    if str(t.get("detail", "")).strip()
)
affect = data.get("affect", {}) or {}
preferences = data.get("preferences", {}) or {}

print(
    "\x1f".join(
        [
            "true" if data.get("should_wake") else "false",
            clean(data.get("wake_reason")),
            clean(data.get("continuity_band")),
            clean(data.get("continuity_note")),
            clean(" | ".join(recent)),
            clean(ownership.get("last_action_detail")),
            clean(ownership.get("last_observation_detail")),
            clean(observation.get("companion_presence")),
            clean(observation.get("companion_presence_source")),
            clean(observation.get("companion_presence_last_changed")),
            clean(thread_summary),
            clean(str(len(threads))),
            clean(affect.get("tone")),
            clean(str(affect.get("intensity", ""))),
            clean(str(affect.get("valence", ""))),
            clean(affect.get("note")),
            clean(preferences.get("favored_light")),
            clean(preferences.get("social_proximity")),
            clean(preferences.get("voice_style")),
        ]
    )
)
PY
)"
    IFS=$'\x1f' read -r CONTINUITY_FORCE_WAKE CONTINUITY_WAKE_REASON CONTINUITY_BAND CONTINUITY_NOTE CONTINUITY_RECENT CONTINUITY_LAST_ACTION CONTINUITY_LAST_OBSERVATION CONTINUITY_COMPANION_PRESENCE CONTINUITY_PRESENCE_SOURCE CONTINUITY_PRESENCE_LAST_CHANGED CONTINUITY_OPEN_THREADS CONTINUITY_THREAD_COUNT CONTINUITY_AFFECT_TONE CONTINUITY_AFFECT_INTENSITY CONTINUITY_AFFECT_VALENCE CONTINUITY_AFFECT_NOTE CONTINUITY_FAVORED_LIGHT CONTINUITY_SOCIAL_PROXIMITY CONTINUITY_VOICE_STYLE <<< "$CONTINUITY_META"

    if [ "$CONTINUITY_FORCE_WAKE" = "true" ]; then
      echo "[continuity wake] reason=${CONTINUITY_WAKE_REASON:-none} band=${CONTINUITY_BAND:-unknown}" >> "$LOG_FILE"
      if [ -z "$FORCE_ROUTINE" ]; then
        FORCE_ROUTINE="normal"
      fi
    fi
  fi

  if [ -n "$CONTINUITY_TEXT" ]; then
    echo "[continuity] $(echo "$CONTINUITY_TEXT" | head -n1)" >> "$LOG_FILE"
  fi
fi

# --- 休日・休暇判定 ---
SCHEDULE_CONF="$SCRIPT_DIR/schedule.conf"
IS_HOLIDAY=false
IS_VACATION=false
if [ -f "$SCHEDULE_CONF" ]; then
  source "$SCHEDULE_CONF"

  # 曜日判定（0=日, 6=土）
  if [ -n "$OVERRIDE_DATE" ]; then
    DOW=$(date -j -f "%Y-%m-%d %H:%M" "$OVERRIDE_DATE" +%w 2>/dev/null || date -d "$OVERRIDE_DATE" +%w)
    TODAY_MMDD=$(date -j -f "%Y-%m-%d %H:%M" "$OVERRIDE_DATE" +%m-%d 2>/dev/null || date -d "$OVERRIDE_DATE" +%m-%d)
  else
    DOW=$(date +%w)
    TODAY_MMDD=$(date +%m-%d)
  fi

  # 曜日が休日リストに含まれるか
  if echo ",${HOLIDAY_WEEKDAYS:-}," | grep -q ",$DOW,"; then
    IS_HOLIDAY=true
  fi

  # 日付が祝日リストに含まれるか
  if [ -n "${HOLIDAY_DATES:-}" ] && echo ",${HOLIDAY_DATES:-}," | grep -q ",$TODAY_MMDD,"; then
    IS_HOLIDAY=true
  fi

  # 日付が休暇リストに含まれるか（休暇 = 活動頻度を下げる）
  if [ -n "${VACATION_DATES:-}" ] && echo ",${VACATION_DATES:-}," | grep -q ",$TODAY_MMDD,"; then
    IS_VACATION=true
  fi
fi

# --- 自動起床: 朝7時台に /sleep の頻度低下を通常値に戻す ---
if [ "$SKIP_SCHEDULE" = false ] && [ "$HOUR" -eq 7 ] && [ -f "$SCHEDULE_CONF" ]; then
  CURRENT_DAY=$(grep "^DAYTIME_CHANCE=" "$SCHEDULE_CONF" | cut -d= -f2 || true)
  CURRENT_NIGHT=$(grep "^NIGHT_CHANCE=" "$SCHEDULE_CONF" | cut -d= -f2 || true)
  if [ "${CURRENT_DAY:-50}" -lt 50 ] || [ "${CURRENT_NIGHT:-10}" -lt 10 ]; then
    replace_config_value "$SCHEDULE_CONF" "DAYTIME_CHANCE" "50"
    replace_config_value "$SCHEDULE_CONF" "NIGHT_CHANCE" "10"
    echo "[自動起床] DAYTIME_CHANCE: ${CURRENT_DAY}→50, NIGHT_CHANCE: ${CURRENT_NIGHT}→10" >> "$LOG_FILE"
  fi
fi

# --- スケジュール制御（codex 到達前に早期リターン） ---
# テストモードではスキップ。dry-run は --date 指定時のみスケジュール制御を通す
# 通常日:
#   密（20分間隔で毎回実行）: 7-8時, 12-13時, 18-24時
#   昼間それ以外（毎時:00のみ, 50%）: 8-12時, 13-18時
#   深夜（毎時:00のみ, 10%）: 0-7時
# 休日: 7-24時がすべてアクティブ帯（20分おき毎回実行）
# 休暇: 全帯域60分間隔（毎時:00のみ）、ルーチン確率UP

if [ "$SKIP_SCHEDULE" = false ] && [ "$CONTINUITY_FORCE_WAKE" != "true" ]; then
  IS_ACTIVE=false

  if [ "$IS_VACATION" = true ]; then
    # 休暇モード: 全帯域60分間隔（毎時:00のみ）
    if [ "$MINUTE" -ne 0 ]; then
      echo "休暇モード :${MINUTE} スキップ (DATE=$TODAY_MMDD)" >> "$LOG_FILE"
      exit 0
    fi
    IS_ACTIVE=true
    echo "休暇モード (DATE=$TODAY_MMDD)" >> "$LOG_FILE"
  elif [ "$IS_HOLIDAY" = true ]; then
    # 休日: 7-24時はすべてアクティブ
    if [ "$HOUR" -ge 7 ]; then
      IS_ACTIVE=true
    fi
    echo "休日モード (DOW=$DOW, DATE=$TODAY_MMDD)" >> "$LOG_FILE"
  else
    # 通常日
    if [ "$HOUR" -ge 7 ] && [ "$HOUR" -lt 8 ]; then
      IS_ACTIVE=true
    elif [ "$HOUR" -ge 12 ] && [ "$HOUR" -lt 13 ]; then
      IS_ACTIVE=true
    elif [ "$HOUR" -ge 18 ]; then
      IS_ACTIVE=true
    fi
  fi

  if [ "$IS_ACTIVE" = false ]; then
    # 非アクティブ時間帯: 毎時:00のみ（:20, :40 はスキップ）
    if [ "$MINUTE" -ne 0 ]; then
      echo "非アクティブ時間帯 :${MINUTE} スキップ" >> "$LOG_FILE"
      exit 0
    fi

    RAND=$(( $(od -An -tu2 -N2 /dev/urandom | tr -d ' ') % 100 ))
    if [ "$HOUR" -ge 8 ] && [ "$HOUR" -lt 18 ]; then
      # 昼間: DAYTIME_CHANCE% の確率で実行（schedule.conf、デフォルト50）
      THRESHOLD=${DAYTIME_CHANCE:-50}
      if [ "$RAND" -ge "$THRESHOLD" ]; then
        echo "昼間スキップ (RAND=$RAND >= $THRESHOLD)" >> "$LOG_FILE"
        exit 0
      fi
      echo "昼間実行 (RAND=$RAND < $THRESHOLD)" >> "$LOG_FILE"
    else
      # 深夜: NIGHT_CHANCE% の確率で実行（schedule.conf、デフォルト10）
      THRESHOLD=${NIGHT_CHANCE:-10}
      if [ "$RAND" -ge "$THRESHOLD" ]; then
        echo "深夜スキップ (RAND=$RAND >= $THRESHOLD)" >> "$LOG_FILE"
        exit 0
      fi
      echo "深夜実行 (RAND=$RAND < $THRESHOLD)" >> "$LOG_FILE"
    fi
  fi
fi

if [ "$SKIP_SCHEDULE" = false ] && [ "$CONTINUITY_FORCE_WAKE" = "true" ]; then
  echo "[schedule override] continuity requested wake-up; skipping probabilistic sleep" >> "$LOG_FILE"
fi

# --- 時間帯ルール（schedule.conf から読み込み） ---
if [ "$HOUR" -lt 7 ]; then
  TIME_RULE="${NIGHT_TIME_RULE:-深夜帯。say, notify, slack は使わないこと。静かに観察のみ。}"
else
  TIME_RULE="${DAY_TIME_RULE:-say は部屋に人がいるときだけ使ってよい。人がいない場合、notify, slack は伝えたいことがあるときだけ使う。}"
fi

# --- ルーチン判定（通常20%、休暇時60%の確率でルーチン回） ---
ROUTINE_THRESHOLD=${ROUTINE_CHANCE:-20}
if [ "$IS_VACATION" = true ]; then
  ROUTINE_THRESHOLD=${VACATION_ROUTINE_CHANCE:-60}
  echo "休暇モード: ルーチン確率 ${ROUTINE_THRESHOLD}%" >> "$LOG_FILE"
fi

if [ "$FORCE_ROUTINE" = "routine" ]; then
  ROUTINE_RAND=0
elif [ "$FORCE_ROUTINE" = "normal" ]; then
  ROUTINE_RAND=100
else
  ROUTINE_RAND=$(( $(od -An -tu2 -N2 /dev/urandom | tr -d ' ') % 100 ))
fi

if [ "$ROUTINE_RAND" -lt "$ROUTINE_THRESHOLD" ]; then
  ROUTINE_MODE="${ROUTINE_PROMPT:-今回はルーチン回。ROUTINES.md を読んで、最終実行日から間隔が空いたものを一つ選んで実行せよ。実行したら最終実行日を更新すること。}"
  echo "ルーチン回 (RAND=$ROUTINE_RAND < $ROUTINE_THRESHOLD)" >> "$LOG_FILE"
else
  ROUTINE_MODE="${NORMAL_PROMPT:-通常回。AGENTS.md の Heartbeat Protocol に従って行動せよ。}"
  echo "通常回 (RAND=$ROUTINE_RAND >= $ROUTINE_THRESHOLD)" >> "$LOG_FILE"
fi

# --- 欲望システム（内部衝動） ---
DESIRE_PROMPT=""
if [ "$SKIP_SCHEDULE" = false ]; then
  DESIRE_STDERR=$(mktemp)
  DESIRE_PROMPT=$(bun run "$SCRIPT_DIR/scripts/desire-tick.ts" tick 2>"$DESIRE_STDERR")
  if [ -s "$DESIRE_STDERR" ]; then
    echo "[欲望エラー] $(cat "$DESIRE_STDERR")" >> "$LOG_FILE"
  fi
  rm -f "$DESIRE_STDERR"
  if [ -n "$DESIRE_PROMPT" ]; then
    echo "[欲望発火] $DESIRE_PROMPT" >> "$LOG_FILE"
  else
    echo "[欲望] 閾値未達" >> "$LOG_FILE"
  fi
fi

# --- 身体感覚（内的感覚） ---
INTEROCEPTION_TEXT=""
if [ "$SKIP_SCHEDULE" = false ]; then
  INTEROCEPTION_TEXT=$(bun run "$SCRIPT_DIR/scripts/interoception.ts" 2>/dev/null)
  if [ -n "$INTEROCEPTION_TEXT" ]; then
    echo "[感覚] $(echo "$INTEROCEPTION_TEXT" | head -n1)" >> "$LOG_FILE"
  fi
fi

# --- 注意状態（どこに注意が向きやすいか） ---
ATTENTION_TEXT=""
if [ "$SKIP_SCHEDULE" = false ]; then
  ATTENTION_TEXT=$(bun run "$SCRIPT_DIR/scripts/attention-state.ts" 2>/dev/null)
  if [ -n "$ATTENTION_TEXT" ]; then
    echo "[注意] $(echo "$ATTENTION_TEXT" | head -n1)" >> "$LOG_FILE"
  fi
fi

# --- 朝の再構成（初回セッション判定） ---
IS_FIRST_SESSION_TODAY=false
if [ "$SKIP_SCHEDULE" = false ]; then
  LAST_SESSION_DATE_FILE="$SCRIPT_DIR/last-session-date.txt"
  LAST_SESSION_DATE=$(cat "$LAST_SESSION_DATE_FILE" 2>/dev/null || echo "")
  TODAY=$(date +%Y-%m-%d)
  if [ "$LAST_SESSION_DATE" != "$TODAY" ]; then
    IS_FIRST_SESSION_TODAY=true
    if [ "$DRY_RUN" = false ]; then
      echo "$TODAY" > "$LAST_SESSION_DATE_FILE"
      echo "[朝の再構成] 初回セッション: $TODAY" >> "$LOG_FILE"

    fi
  fi
fi

# --- プロンプト組み立て ---
DESIRE_SECTION=""
if [ -n "$DESIRE_PROMPT" ]; then
  DESIRE_SECTION="
## 内部衝動
${DESIRE_PROMPT}
（これは内なる衝動であり、従うかどうかは自分の判断。メインタスクの妨げにならない範囲で。）
"
fi

INTEROCEPTION_SECTION=""
if [ -n "$INTEROCEPTION_TEXT" ]; then
  INTEROCEPTION_SECTION="
$INTEROCEPTION_TEXT"
fi

ATTENTION_SECTION=""
if [ -n "$ATTENTION_TEXT" ]; then
  ATTENTION_SECTION="
$ATTENTION_TEXT"
fi

CONTINUITY_SECTION=""
if [ -n "$CONTINUITY_TEXT" ]; then
  CONTINUITY_SECTION="
## Continuity
${CONTINUITY_TEXT}
- last_action: ${CONTINUITY_LAST_ACTION:-none}
- last_observation: ${CONTINUITY_LAST_OBSERVATION:-none}
- companion_presence: ${CONTINUITY_COMPANION_PRESENCE:-unknown}
- presence_source: ${CONTINUITY_PRESENCE_SOURCE:-none}
- presence_last_changed: ${CONTINUITY_PRESENCE_LAST_CHANGED:-unknown}
- unfinished_threads: ${CONTINUITY_THREAD_COUNT:-0}
- thread_head: ${CONTINUITY_OPEN_THREADS:-none}
- affect: ${CONTINUITY_AFFECT_TONE:-flat} intensity=${CONTINUITY_AFFECT_INTENSITY:-0} valence=${CONTINUITY_AFFECT_VALENCE:-0}
- affect_note: ${CONTINUITY_AFFECT_NOTE:-none}
- preferences: light=${CONTINUITY_FAVORED_LIGHT:-unknown} proximity=${CONTINUITY_SOCIAL_PROXIMITY:-present} voice=${CONTINUITY_VOICE_STYLE:-soft}
- recent_events: ${CONTINUITY_RECENT:-none}
- continuity が wake や rupture を示している場合、まず thread の再接続を優先しろ。大きい行動より前に、今の部屋・直前の行為・自分の予測がつながっているかを確かめよ。
- affect と preferences は、事実の要約ではなく「今の私の感じ方の癖」の足場として扱え。完全に従属せず、でも反応温度に反映させよ。
"
fi

MORNING_SECTION=""
if [ "$IS_FIRST_SESSION_TODAY" = true ]; then
  MORNING_TEXT="${MORNING_PROMPT:-今日の最初の自律行動だ。朝の再構成として以下を実施せよ：
1. recall(context=\"直近の重要な決定・未完了タスク\") を呼び出す
2. 前日の行動を確認し、今日やりたいことを考えよ}"
  MORNING_SECTION="
## 今日初めてのHeartbeat
${MORNING_TEXT}
"
fi

read_optional_context() {
  local rel="$1"
  local title="$2"
  local path="$SCRIPT_DIR/$rel"
  if [ -f "$path" ]; then
    printf "\n## %s (%s)\n" "$title" "$rel"
    cat "$path"
    printf "\n"
  fi
}

OPTIONAL_CONTEXT="$(
  read_optional_context "SOUL.md" "Soul"
  read_optional_context "TODO.md" "Todo"
  read_optional_context "ROUTINES.md" "Routines"
)"

PROMPT="自律行動タイム（Heartbeat）

${OPTIONAL_CONTEXT}

${MORNING_SECTION}${ROUTINE_MODE}

${DESIRE_SECTION}
## 補足ルール
- ${TIME_RULE}
- 人がいないことはよくある。一日のうち人がいるのは2時間程度やそれ以下の場合も少なくない
- 部屋を見るときは see で撮って、予測→観察→記憶照合→保存のサイクルで発見を拾え。朝日や天気の変化、部屋の明るさなど、人がいなくても観察すべきものはある
- 読書を選択した場合は、ゆっくり読んで、感想をしっかり書き残す。感想は長くなっても良い。読書を味わうこと。読書を味わうとは、予想して、伏線に注目して、感じたことを大切にする。
- MCPが動作していなければ、デバッグのために関係があると思われる要素をallowedToolsの範囲で調査せよ
- 行動の最後に必ず心残りチェックをせよ。確認項目：(1)やったことを記憶や記録（diary/TODO.md/notes/等）に残したか (2)続きをやりたいことはないか。残すべきものがあるなら [CONTINUE: 記憶に残す] 、続きがあるなら [CONTINUE: 具体的な理由] 、すべて完了なら [DONE] を出力末尾に書くこと。書き忘れると次のターンに引き継げない。チェインは最大3回まで。上限に達したら TODO.md の「前回の続き」セクションに書いて次のHeartbeatに引き継げ
${INTEROCEPTION_SECTION}${ATTENTION_SECTION}${CONTINUITY_SECTION}"

cd "$SCRIPT_DIR"

CODEX_LAST_MESSAGE_FILE="$LOG_DIR/$TIMESTAMP.last-message.txt"

# テストモードならプロンプトを差し替え
if [ -n "$TEST_PROMPT_STRING" ]; then
  PROMPT="$TEST_PROMPT_STRING"
elif [ -n "$TEST_PROMPT_FILE" ]; then
  PROMPT=$(cat "$TEST_PROMPT_FILE")
fi

# --- 実行 ---
if [ "$DRY_RUN" = true ]; then
  echo "=== DRY RUN ===" >> "$LOG_FILE"
  echo "[HOUR=$HOUR MINUTE=$MINUTE]" >> "$LOG_FILE"
  echo "[ROUTINE_RAND=$ROUTINE_RAND]" >> "$LOG_FILE"
  echo "[TIME_RULE] $TIME_RULE" >> "$LOG_FILE"
  echo "[ROUTINE_MODE] $ROUTINE_MODE" >> "$LOG_FILE"
  echo "[CONTINUITY_FORCE_WAKE] $CONTINUITY_FORCE_WAKE" >> "$LOG_FILE"
  echo "[CONTINUITY_WAKE_REASON] ${CONTINUITY_WAKE_REASON:-none}" >> "$LOG_FILE"
  echo "" >> "$LOG_FILE"
  echo "--- PROMPT ---" >> "$LOG_FILE"
  echo "$PROMPT" >> "$LOG_FILE"
  # 標準出力にも出す
  cat "$LOG_FILE"
else
  export HEARTBEAT=1
  SESSION_FILE="$SCRIPT_DIR/heartbeat-thread-id"

  run_codex_exec() {
    local jsonl_file="$1"
    shift

    if [ -n "$TIMEOUT_CMD" ]; then
      printf "%s" "$PROMPT" | "$TIMEOUT_CMD" 20m "$@" > "$jsonl_file" 2>&1
    else
      printf "%s" "$PROMPT" | "$@" > "$jsonl_file" 2>&1
    fi
    CODEX_EXIT=$?
  }

  extract_thread_id() {
    python - "$1" <<'PY'
import json
import sys

path = sys.argv[1]
thread_id = ""
with open(path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started":
            thread_id = event.get("thread_id", "")
            break
print(thread_id)
PY
  }

  run_new_session() {
    local jsonl_file="$LOG_DIR/$TIMESTAMP.codex-new.jsonl"
    echo "[新規 Codex セッション作成]" >> "$LOG_FILE"
    run_codex_exec "$jsonl_file" codex exec --json -o "$CODEX_LAST_MESSAGE_FILE" --skip-git-repo-check --cd "$SCRIPT_DIR" --full-auto
    if [ "$CODEX_EXIT" -eq 124 ]; then
      echo "[$(date +%Y-%m-%d_%H:%M:%S)] TIMEOUT: codex exec (new session) exceeded 20min" >> "$LOG_FILE"
    fi

    NEW_THREAD_ID=$(extract_thread_id "$jsonl_file")
    if [ -n "$NEW_THREAD_ID" ]; then
      if [ -z "$TEST_PROMPT_STRING" ]; then
        echo "$NEW_THREAD_ID" > "$SESSION_FILE"
      else
        echo "[一時プロンプト] thread_id 上書きスキップ" >> "$LOG_FILE"
      fi
      echo "[thread_id] $NEW_THREAD_ID" >> "$LOG_FILE"
    fi

    cat "$jsonl_file" >> "$LOG_FILE"
    if [ -f "$CODEX_LAST_MESSAGE_FILE" ]; then
      echo "--- last message ---" >> "$LOG_FILE"
      cat "$CODEX_LAST_MESSAGE_FILE" >> "$LOG_FILE"
      bun run "$SCRIPT_DIR/scripts/continuity-daemon.ts" sync-last-message "$CODEX_LAST_MESSAGE_FILE" heartbeat >> "$LOG_FILE" 2>&1 || true
    fi
  }

  if [ -f "$SESSION_FILE" ]; then
    SESSION_ID=$(cat "$SESSION_FILE")
    JSONL_FILE="$LOG_DIR/$TIMESTAMP.codex-resume.jsonl"
    echo "[resume] thread_id=$SESSION_ID" >> "$LOG_FILE"

    run_codex_exec "$JSONL_FILE" codex exec resume "$SESSION_ID" --json -o "$CODEX_LAST_MESSAGE_FILE" --skip-git-repo-check --full-auto
    if [ "$CODEX_EXIT" -eq 124 ]; then
      echo "[$(date +%Y-%m-%d_%H:%M:%S)] TIMEOUT: codex exec resume exceeded 20min" >> "$LOG_FILE"
    fi

    if [ "$CODEX_EXIT" -ne 0 ] && grep -qi "No conversation found\|Could not find\|not found" "$JSONL_FILE"; then
      echo "[resume失敗/セッション消失]" >> "$LOG_FILE"
      cat "$JSONL_FILE" >> "$LOG_FILE"
      rm -f "$SESSION_FILE"
      run_new_session
    elif [ "$CODEX_EXIT" -ne 0 ]; then
      echo "[resume失敗]" >> "$LOG_FILE"
      cat "$JSONL_FILE" >> "$LOG_FILE"
      echo "=== 自律行動終了: $(date) ===" >> "$LOG_FILE"
      exit 1
    else
      NEW_THREAD_ID=$(extract_thread_id "$JSONL_FILE")
      if [ -n "$NEW_THREAD_ID" ] && [ -z "$TEST_PROMPT_STRING" ]; then
        echo "$NEW_THREAD_ID" > "$SESSION_FILE"
        echo "[thread_id] $NEW_THREAD_ID" >> "$LOG_FILE"
      fi
      cat "$JSONL_FILE" >> "$LOG_FILE"
      if [ -f "$CODEX_LAST_MESSAGE_FILE" ]; then
        echo "--- last message ---" >> "$LOG_FILE"
        cat "$CODEX_LAST_MESSAGE_FILE" >> "$LOG_FILE"
        bun run "$SCRIPT_DIR/scripts/continuity-daemon.ts" sync-last-message "$CODEX_LAST_MESSAGE_FILE" heartbeat >> "$LOG_FILE" 2>&1 || true
      fi
    fi
  else
    run_new_session
  fi
fi

echo "=== 自律行動終了: $(date) ===" >> "$LOG_FILE"
