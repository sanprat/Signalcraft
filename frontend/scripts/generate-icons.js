const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

const sizes = [72, 96, 128, 144, 152, 192, 384, 512];
const outputDir = path.join(__dirname, '../public/icons');

// Create output directory if it doesn't exist
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

// Create a simple SVG icon with "SC" text
const createSVG = (size) => {
  return `
    <svg width="${size}" height="${size}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#10B981;stop-opacity:1" />
          <stop offset="100%" style="stop-color:#047857;stop-opacity:1" />
        </linearGradient>
      </defs>
      <rect width="${size}" height="${size}" rx="${size * 0.2}" fill="url(#grad)"/>
      <text x="50%" y="50%" 
            font-family="Arial, sans-serif" 
            font-size="${size * 0.4}" 
            font-weight="bold"
            fill="white" 
            text-anchor="middle" 
            dominant-baseline="central">SC</text>
    </svg>
  `;
};

async function generateIcons() {
  console.log('Generating PWA icons...');
  
  for (const size of sizes) {
    const svg = createSVG(size);
    const filename = path.join(outputDir, `icon-${size}x${size}.png`);
    
    try {
      await sharp(Buffer.from(svg))
        .resize(size, size)
        .png()
        .toFile(filename);
      
      const stats = fs.statSync(filename);
      console.log(`✓ Generated icon-${size}x${size}.png (${(stats.size / 1024).toFixed(1)} KB)`);
    } catch (error) {
      console.error(`✗ Failed to generate icon-${size}x${size}.png:`, error.message);
    }
  }
  
  console.log('\nAll icons generated successfully!');
}

generateIcons().catch(console.error);
