#!/bin/zsh
# 한글 폰트(OFL 라이선스)를 fonts/ 에 내려받는다. 생성기가 @font-face 로 사용.
#   ./scripts/download_fonts.sh
# 학습용(train) 폰트와 일반화 평가용(ood) 폰트는 src/ko_table_vlm/styles.py 에서 나눈다.
set -e
cd "$(dirname "$0")/.."
mkdir -p fonts
BASE="https://raw.githubusercontent.com/google/fonts/main/ofl"
typeset -A FONTS=(
  NotoSansKR.ttf        "notosanskr/NotoSansKR%5Bwght%5D.ttf"
  NotoSerifKR.ttf       "notoserifkr/NotoSerifKR%5Bwght%5D.ttf"
  NanumGothic.ttf       "nanumgothic/NanumGothic-Regular.ttf"
  NanumMyeongjo.ttf     "nanummyeongjo/NanumMyeongjo-Regular.ttf"
  NanumGothicCoding.ttf "nanumgothiccoding/NanumGothicCoding-Regular.ttf"
  GowunBatang.ttf       "gowunbatang/GowunBatang-Regular.ttf"
  GowunDodum.ttf        "gowundodum/GowunDodum-Regular.ttf"
  IBMPlexSansKR.ttf     "ibmplexsanskr/IBMPlexSansKR-Regular.ttf"
)
for name in ${(k)FONTS}; do
  if [[ -s "fonts/$name" ]]; then echo "skip  $name"; continue; fi
  curl -fsSL -o "fonts/$name" "$BASE/${FONTS[$name]}" && echo "ok    $name" || echo "FAIL  $name"
done
