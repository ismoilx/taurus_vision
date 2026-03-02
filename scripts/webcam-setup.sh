#!/usr/bin/env bash
# =============================================================================
# Taurus Vision — Webcam Setup & Diagnostics Script
# =============================================================================
#
# MAQSAD:
#   Host mashinadagi USB/webcam qurilmalarni avtomatik aniqlaydi va
#   docker-compose.webcam.yml faylini yangilaydi.
#
# ISHLATISH:
#   chmod +x scripts/webcam-setup.sh    # Bir marta
#   ./scripts/webcam-setup.sh           # Qurilmalarni aniqlash
#   make setup-webcam                   # Makefile orqali
#
# NIMA QILADI:
#   1. /dev/video* qurilmalarini skanerlaydi
#   2. Har bir qurilma haqida ma'lumot ko'rsatadi (v4l2-ctl)
#   3. docker-compose.webcam.yml faylini yangilaydi
#   4. Containerni qayta ishga tushiradi (ixtiyoriy)
#
# =============================================================================
set -euo pipefail

# ── Ranglar ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'  # No Color

# ── Konstantalar ─────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OVERRIDE_FILE="$PROJECT_ROOT/docker-compose.webcam.yml"

# ── Helper funksiyalar ────────────────────────────────────────────────────────

log_info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }
log_section() { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }

# ── 1. QURILMALARNI SKANERLASH ───────────────────────────────────────────────

log_section "Video qurilmalarni skanerlash"

declare -a VIDEO_DEVICES=()

for device in /dev/video*; do
    if [[ -c "$device" ]]; then
        VIDEO_DEVICES+=("$device")
        log_info "Topildi: $device"
    fi
done

if [[ ${#VIDEO_DEVICES[@]} -eq 0 ]]; then
    log_error "Hech qanday video qurilma topilmadi."
    echo ""
    echo "  Tekshiring:"
    echo "  1. USB kamerani ulang"
    echo "  2. $ ls -la /dev/video*"
    echo "  3. $ lsusb | grep -i camera"
    echo ""
    exit 1
fi

echo ""
log_info "Jami ${#VIDEO_DEVICES[@]} ta video qurilma topildi."

# ── 2. QURILMA MA'LUMOTLARI ──────────────────────────────────────────────────

log_section "Qurilma tafsilotlari"

for device in "${VIDEO_DEVICES[@]}"; do
    echo -e "\n  ${BLUE}$device${NC}"

    # Qurilma ruxsatlari
    perms=$(stat -c "%A %U:%G" "$device" 2>/dev/null || echo "?")
    echo "    Ruxsat:  $perms"

    # Video guruhi GID
    video_gid=$(getent group video 2>/dev/null | cut -d: -f3 || echo "44")
    echo "    video GID: $video_gid"

    # v4l2-ctl mavjud bo'lsa — kamera nomi
    if command -v v4l2-ctl &>/dev/null; then
        cam_name=$(v4l2-ctl --device="$device" --info 2>/dev/null \
                   | grep "Card type" | awk -F: '{print $2}' | xargs || echo "Noma'lum")
        echo "    Ism:     $cam_name"
    fi
done

# ── 3. DOCKER GURUHI TEKSHIRUVI ──────────────────────────────────────────────

log_section "Docker ruxsatlar tekshiruvi"

# Docker daemon video guruhga kirishini tekshirish
video_gid=$(getent group video 2>/dev/null | cut -d: -f3 || echo "44")

# Joriy foydalanuvchi video guruhda?
if id -Gn "$USER" 2>/dev/null | grep -q '\bvideo\b'; then
    log_info "Foydalanuvchi '$USER' video guruhida ✓"
else
    log_warn "Foydalanuvchi '$USER' video guruhida EMAS."
    echo "       Hal qilish: sudo usermod -aG video $USER && newgrp video"
fi

# ── 4. docker-compose.webcam.yml GENERATSIYA ─────────────────────────────────

log_section "docker-compose.webcam.yml yaratilmoqda"

# devices ro'yxatini build qilish
DEVICES_YAML=""
for device in "${VIDEO_DEVICES[@]}"; do
    DEVICES_YAML+="      - ${device}:${device}\n"
done

cat > "$OVERRIDE_FILE" << EOF
# ============================================================================
# Taurus Vision — Webcam Override (Avtomatik generatsiya)
# Yaratildi: $(date '+%Y-%m-%d %H:%M:%S')
# Skript: scripts/webcam-setup.sh
#
# ISHLATISH:
#   make up-webcam
#   # yoki:
#   docker compose -f docker-compose.yml -f docker-compose.webcam.yml up -d
# ============================================================================

services:
  backend:
    # Avtomatik aniqlangan video qurilmalar:
    devices:
$(printf '%s' "$DEVICES_YAML")
    group_add:
      - video
EOF

log_info "Fayl yaratildi: $OVERRIDE_FILE"

echo ""
cat "$OVERRIDE_FILE"

# ── 5. KEYINGI QADAM ─────────────────────────────────────────────────────────

log_section "Keyingi qadam"

echo ""
echo "  Tizimni webcam bilan qayta ishga tushirish:"
echo ""
echo -e "  ${GREEN}make up-webcam-build${NC}   (birinchi marta — to'liq build)"
echo -e "  ${GREEN}make up-webcam${NC}         (keyingi safar — tezroq)"
echo ""
echo "  Webcam qurilmani API orqali tekshirish:"
echo -e "  ${GREEN}curl http://localhost:8000/api/v1/cameras/detect-webcams${NC}"
echo ""

# ── 6. IXTIYORIY: RESTART ─────────────────────────────────────────────────────

read -r -p "Hoziroq containerni qayta ishga tushirasizmi? [y/N] " response
if [[ "$response" =~ ^[Yy]$ ]]; then
    log_info "Container qayta ishga tushirilmoqda..."
    cd "$PROJECT_ROOT"
    docker compose -f docker-compose.yml -f docker-compose.webcam.yml up -d --build backend
    log_info "Backend qayta ishga tushirildi. ✓"
    echo ""
    log_info "Loglarni kuzating:"
    echo "  make logs-backend"
else
    log_info "Qo'lda ishga tushirish uchun:"
    echo "  make up-webcam-build"
fi