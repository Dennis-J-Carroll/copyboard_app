#!/usr/bin/env python3
"""
Generate placeholder icons for the Copyboard browser extension.
This creates simple PNG icons with dimensions 16x16, 48x48, and 128x128.
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, output_path):
    """Create a simple clipboard icon with the given size"""
    # Create a new image with transparent background
    img = Image.new('RGBA', (size, size), color=(255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Calculate dimensions
    padding = int(size * 0.1)
    width = size - 2 * padding
    height = size - 2 * padding
    
    # Draw clipboard outline (rectangle with clip at top)
    outline_color = (74, 108, 247, 255)  # Blue color
    fill_color = (255, 255, 255, 180)  # Semi-transparent white
    
    # Main rectangle (clipboard body)
    draw.rectangle(
        [(padding, padding + int(height * 0.15)), 
         (padding + width, padding + height)],
        fill=fill_color,
        outline=outline_color,
        width=max(1, int(size * 0.05))
    )
    
    # Top clip
    clip_width = width // 3
    clip_height = int(height * 0.15)
    clip_x = padding + (width - clip_width) // 2
    draw.rectangle(
        [(clip_x, padding), 
         (clip_x + clip_width, padding + clip_height)],
        fill=fill_color,
        outline=outline_color,
        width=max(1, int(size * 0.05))
    )
    
    # Draw lines to represent text on clipboard if size is big enough
    if size >= 48:
        line_padding = int(height * 0.1)
        line_height = max(1, int(height * 0.05))
        line_spacing = int(height * 0.15)
        line_inset = int(width * 0.15)
        
        for i in range(3):
            y_pos = padding + clip_height + line_padding + i * line_spacing
            draw.rectangle(
                [(padding + line_inset, y_pos), 
                 (padding + width - line_inset, y_pos + line_height)],
                fill=outline_color
            )
    
    # Create directories if they don't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save the image
    img.save(output_path, 'PNG')

def main():
    """Generate icons in different sizes"""
    # Base directory for icons
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)  # Move up one level from scripts directory
    icons_dir = os.path.join(project_root, 'copyboard_extension', 'browser_extension', 'icons')
    
    # Ensure the icons directory exists
    os.makedirs(icons_dir, exist_ok=True)
    
    # Generate icons in different sizes
    sizes = [16, 48, 128]
    for size in sizes:
        output_path = os.path.join(icons_dir, f'icon{size}.png')
        create_icon(size, output_path)
        print(f"Created icon: {output_path}")

if __name__ == "__main__":
    main()
