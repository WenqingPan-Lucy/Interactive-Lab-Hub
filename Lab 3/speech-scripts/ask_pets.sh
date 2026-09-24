set -euo pipefail

VOICES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/voices"
python3 -m piper \
  --model en_US-lessac-medium \
  --data-dir "$VOICES_DIR" \
  --output-raw \
  -- "How many pets do you have?" \
  | aplay -r 22050 -f S16_LE -t raw -

# Record the respondent's answer for 5 seconds
echo "Recording your answer for 5 seconds..."
arecord -d 5 -f cd -c 1 -r 16000 pets_answer.wav

echo "Answer saved to pets_answer.wav"