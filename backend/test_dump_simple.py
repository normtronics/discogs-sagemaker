#!/usr/bin/env python3
"""
Simple test to see what's in the dump file
"""
import gzip
import xml.etree.ElementTree as ET
import sys

dump_path = '../data/discogs_releases.xml.gz'

print(f"Testing dump file: {dump_path}\n")

try:
    with gzip.open(dump_path, 'rb') as f:
        print("✓ File opened successfully")
        
        # Try to parse first few releases
        count = 0
        for event, elem in ET.iterparse(f, events=('end',)):
            if elem.tag == 'release':
                count += 1
                
                # Show first release details
                if count == 1:
                    print(f"\nFirst release found:")
                    print(f"  Tag: {elem.tag}")
                    print(f"  ID: {elem.get('id')}")
                    
                    title = elem.find('title')
                    print(f"  Title: {title.text if title is not None else 'None'}")
                    
                    # Check for images
                    images_elem = elem.find('images')
                    if images_elem is not None:
                        image_count = len(list(images_elem.findall('image')))
                        print(f"  Images element: Found")
                        print(f"  Image count: {image_count}")
                        
                        # Show first image
                        first_img = images_elem.find('image')
                        if first_img is not None:
                            print(f"  First image URI: {first_img.get('uri')}")
                            print(f"  First image type: {first_img.get('type')}")
                    else:
                        print(f"  Images element: NOT FOUND")
                
                # Stop after finding 10 releases
                if count >= 10:
                    break
                
                elem.clear()
        
        print(f"\n✓ Found {count} releases in dump")
        
        if count == 0:
            print("\n✗ No releases found! The dump file might be:")
            print("  1. Empty or corrupted")
            print("  2. Wrong format")
            print("  3. Still downloading")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

