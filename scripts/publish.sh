#!/usr/bin/env bash
set -e

# CodeMorph Publishing Tool
# Automates the build and upload of codemorph to PyPI.

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0;34m' # Blue
RESET='\033[0m'

echo -e "${NC}======================================================${RESET}"
echo -e "${NC}              CodeMorph PyPI Publishing Tool          ${RESET}"
echo -e "${NC}======================================================${RESET}"

# 1. Check for required build tools
echo -e "\n${YELLOW}[1/4] Checking packaging dependencies...${RESET}"
if ! python3 -c "import build" &> /dev/null; then
    echo -e "${YELLOW}Installing 'build' module...${RESET}"
    pip install build
fi

if ! python3 -c "import twine" &> /dev/null; then
    echo -e "${YELLOW}Installing 'twine' module...${RESET}"
    pip install twine
fi
echo -e "${GREEN}✓ Build and Twine are installed.${RESET}"

# 2. Clean old distribution artifacts
echo -e "\n${YELLOW}[2/4] Cleaning previous builds...${RESET}"
rm -rf dist/ build/ *.egg-info/
echo -e "${GREEN}✓ Distribution directories cleared.${RESET}"

# 3. Build Source Distribution and Wheel
echo -e "\n${YELLOW}[3/4] Building packages...${RESET}"
python3 -m build
echo -e "${GREEN}✓ Distribution built successfully.${RESET}"

# 4. Check outputs with Twine
echo -e "\n${YELLOW}[4/4] Verifying packages with Twine...${RESET}"
python3 -m twine check dist/*
echo -e "${GREEN}✓ Twine checks passed.${RESET}"

# 5. Offer upload options
echo -e "\n${NC}======================================================${RESET}"
echo -e "Choose an option to upload the package:"
echo -e "  1) Upload to TestPyPI (Recommended first step)"
echo -e "  2) Upload to Production PyPI"
echo -e "  3) Exit without uploading"
read -rp "Enter selection [1-3]: " choice

case $choice in
    1)
        echo -e "\n${YELLOW}Uploading to TestPyPI...${RESET}"
        python3 -m twine upload --repository testpypi dist/*
        echo -e "${GREEN}✓ Upload completed to TestPyPI.${RESET}"
        ;;
    2)
        echo -e "\n${RED}Uploading to Production PyPI...${RESET}"
        python3 -m twine upload dist/*
        echo -e "${GREEN}✓ Upload completed to PyPI.${RESET}"
        ;;
    *)
        echo -e "\n${YELLOW}Build generated. You can upload manually from dist/* using twine.${RESET}"
        ;;
esac
