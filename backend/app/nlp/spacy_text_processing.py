"""Legacy PDF text processing utilities.

DEPRECATED: This module is legacy code and is no longer used in the current pipeline.
The current pipeline uses SpacyLayoutPDFParser in pdf_parser.py instead.
This file is kept for reference but should not be imported.
"""

from collections import defaultdict
from pathlib import Path
import spacy
from spacy.tokens import Doc
from spacy_layout import spaCyLayout
import warnings
import os
warnings.filterwarnings("ignore", category=UserWarning)
ncpu = int(os.cpu_count() or None)
os.environ['OMP_NUM_THREADS'] = str(min([3, ncpu]))
os.environ['MKL_NUM_THREADS'] = str(min([3, ncpu]))

# DEPRECATED: This global load is legacy code
nlp = spacy.load("en_core_web_lg")
layout = spaCyLayout( nlp, headings=["section_header", "title", "page_header"],separator="\n\n")

def extract_sections(doc: Doc):
    """Extract main text sections from scientific paper."""
    sections = defaultdict(list)
    current_section = "introduction"  # Default section
    
    for span in doc.spans["layout"]:
        # Skip non-text elements
        if span.label_ not in ["text", "section_header"]:
            continue
            
        # Handle section headers
        if span.label_ == "section_header":
            section_name = span.text.lower().strip()
            # Normalize common section names
            if any(keyword in section_name for keyword in ["intro", "background"]):
                current_section = "introduction"
            elif any(keyword in section_name for keyword in ["method", "material", "experiment"]):
                current_section = "methods"
            elif any(keyword in section_name for keyword in ["result", "finding"]):
                current_section = "results"
            elif any(keyword in section_name for keyword in ["discuss", "conclusion"]):
                current_section = "discussion"
            else:
                current_section = section_name
                
        # Add text to current section
        elif span.label_ == "text":
            # Get the closest heading for better section assignment
            if span._.heading:
                heading_text = span._.heading.lower()
                # Use heading to refine section assignment
                for keyword, section in [
                    (["intro", "background"], "introduction"),
                    (["method", "material", "experiment"], "methods"),
                    (["result", "finding"], "results"),
                    (["discuss", "conclusion"], "discussion")
                ]:
                    if any(k in heading_text for k in keyword):
                        current_section = section
                        break
            
            sections[current_section].append(span.text)
    
    # Join text within each section
    return {section: " ".join(texts) for section, texts in sections.items()}

def clean_document_text(doc):
    """Remove headers, footers, author info, and other metadata"""
    clean_spans = []
    
    for span in doc.spans["layout"]:
        # Skip unwanted content types
        if span.label_ in [
            "page_header", "page_footer", "footnote", 
            "page_number", "reference", "bibliography"
        ]:
            continue
            
        # Filter by position - remove very top/bottom content [web:92][web:94]
        layout_info = span._.layout
        if layout_info and hasattr(layout_info, 'bbox'):
            bbox = layout_info.bbox
            page_height = layout_info.page.height if hasattr(layout_info, 'page') else 1000
            
            # Skip content in top 10% or bottom 10% of page (likely headers/footers)
            if bbox.y1 < page_height * 0.1 or bbox.y0 > page_height * 0.9:
                continue
        
        # Filter by content patterns
        text = span.text.strip()
        if (
            # Skip short fragments (likely metadata)
            len(text) < 20 or
            # Skip author information patterns
            re.match(r'^[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+', text) or
            # Skip email patterns
            '@' in text and len(text.split()) < 10 or
            # Skip page numbers
            re.match(r'^\d+$', text) or
            # Skip copyright/journal info
            any(keyword in text.lower() for keyword in [
                'copyright', '©', 'journal', 'volume', 'doi:', 
                'manuscript', 'submitted', 'accepted'
            ])
        ):
            continue
            
        clean_spans.append(span)
    
    return clean_spans

def extract_figure_captions(doc):
    """Extract figure captions separately from main text"""
    captions = []
    
    for span in doc.spans["layout"]:
        text = span.text.strip()
        
        # Identify figure captions by pattern [web:84]
        if (
            span.label_ in ["caption", "figure"] or
            re.match(r'^(Figure|Fig\.?|Table)\s+\d+', text, re.IGNORECASE) or
            re.match(r'^(Panel|Supplementary)\s+', text, re.IGNORECASE)
        ):
            captions.append({
                'type': 'figure_caption',
                'text': text,
                'position': span.start_char,
                'layout': span._.layout
            })
    
    return captions

def fix_geographic_symbols(text):
    """Fix degree and second symbols for coordinate extraction"""
    # Common PDF encoding issues for geographic symbols
    symbol_fixes = {
        # Degree symbol variants
        '°': '°',  # Ensure proper Unicode
        '\u00b0': '°',  # Standard degree
        '\u2103': '°C',  # Celsius
        'Â°': '°',  # Common encoding issue
        'â°': '°',
        '&deg;': '°',  # HTML entity
        
        # Second/minute symbols
        '″': '"',  # Double prime (seconds)
        '′': "'",  # Prime (minutes)  
        '\u2033': '"',  # Double prime Unicode
        '\u2032': "'",  # Prime Unicode
        '&prime;': "'",
        '&Prime;': '"',
        
        # Fix common coordinate separators
        'Â ': ' ',  # Non-breaking space issues
        '\xa0': ' ',  # Non-breaking space
    }
    
    for wrong, correct in symbol_fixes.items():
        text = text.replace(wrong, correct)
    
    return text

def process_scientific_pdf(pdf_path: Path):
    """Complete pipeline for scientific PDF processing"""
    
    # Process document
    doc = layout(pdf_path)
    doc = nlp(doc)
    
    # Clean and extract sections
    clean_spans = clean_document_text(doc)
    
    # Extract figure captions separately
    captions = extract_figure_captions(doc)
    
    # Process sections
    section_text = {}
    current_section = "introduction"
    
    for span in clean_spans:
        if span.label_ == "text":
            # Fix geographic symbols
            clean_text = fix_geographic_symbols(span.text)
            
            # Determine section from heading context
            if span._.heading:
                heading = span._.heading.lower()
                if any(word in heading for word in ["method", "material"]):
                    current_section = "methods"
                elif any(word in heading for word in ["result", "finding"]):
                    current_section = "results"
                elif any(word in heading for word in ["discuss", "conclusion"]):
                    current_section = "discussion"
            
            if current_section not in section_text:
                section_text[current_section] = []
            section_text[current_section].append(clean_text)
    
    # Join text within sections for complete spans
    sections = {
        section: " ".join(texts) 
        for section, texts in section_text.items()
    }
    
    return {
        'sections': sections,
        'captions': captions,
        'full_doc': doc
    }

# Usage
result = process_scientific_pdf("paper.pdf")

# Access clean section text
intro_text = result['sections']['introduction']
methods_text = result['sections']['methods']

# Access figure captions separately
figure_captions = result['captions']


def main():
    # Example usage with a sample PDF in the pdf directory
    pdf_path = next(iter((Path.cwd() / "zotero_files").glob("*.pdf")))
    doc = layout(pdf_path)
    doc = nlp(doc)

if __name__ == "__main__":
    main()


