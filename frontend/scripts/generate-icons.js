#!/usr/bin/env node
// Simple icon generator for PWA
const fs = require('fs');
const path = require('path');

// Create placeholder PNG icons (in production, use real icon files)
const sizes = [72, 96, 128, 144, 152, 192, 384, 512];
const iconsDir = path.join(__dirname, 'public/icons');

// Create a simple colored square as placeholder
function createPlaceholderIcon(size) {
    // Minimal valid PNG (1x1 emerald green pixel, will be scaled)
    // This is a placeholder - in production use real icons
    const pngHeader = Buffer.from([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0xD7, 0x63, 0x10, 0x15, 0x15, 0x05,
        0x00, 0x01, 0x11, 0x00, 0x7D, 0xC4, 0x52, 0x8E,
        0x51, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
        0x44, 0xAE, 0x42, 0x60, 0x82
    ]);
    
    // For now, just create a note that real icons are needed
    const notePath = path.join(iconsDir, 'README.md');
    fs.writeFileSync(notePath, `# PWA Icons

Generate icons in the following sizes:
${sizes.join(', ')}

You can use:
1. Online generators: https://realfavicongenerator.net/
2. Figma/Sketch: Export at each size
3. ImageMagick: convert icon.svg -resize ${size}x${size} icon-${size}x${size}.png

Icon should be:
- Emerald green gradient background (#10B981 to #047857)
- White "SC" letters in center
- Rounded corners (handled by maskable purpose)
`);
}

sizes.forEach(size => {
    const iconPath = path.join(iconsDir, `icon-${size}x${size}.png`);
    if (!fs.existsSync(iconPath)) {
        console.log(`Placeholder needed: ${iconPath}`);
    }
});

createPlaceholderIcon();
console.log('Icon generation note created. Please add real PNG icons for production.');
