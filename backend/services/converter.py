import os
import re
import pdfplumber
import pymupdf  # type: ignore
import structlog
from typing import List, Tuple, Optional, Dict, Any
from collections import defaultdict

logger = structlog.get_logger()


class DocumentConverter:
    def __init__(self):
        # Configuration for header detection
        self.header_size_threshold_large = 1.3  # Relative to average
        self.header_size_threshold_medium = 1.15
        self.header_size_threshold_small = 1.08
        
        # Pattern for section numbers (1., 1.1, 1.1.1, etc.)
        self.section_number_pattern = re.compile(r'^(\d+(\.\d+)*\.?)$')
        # Pattern for numbered headers (MUST have at least one dot to avoid matching addresses)
        # Matches: "20. TEXT", "1.1 TEXT", "1.1.1. TEXT"
        # Doesn't match: "5265 Street Name" (no dots)
        self.numbered_header_pattern = re.compile(r'^(\d+(?:\.\d+)+\.?|\d+\.)\s+')

    def convert_pdf_to_markdown(
        self,
        pdf_path: str,
        output_dir: str,
        image_output_dir: str,
        public_image_path: str,
        custom_filename: Optional[str] = None,
    ) -> str:
        """
        Convert a PDF file to Markdown with high accuracy using pdfplumber.

        This implementation uses:
        - pdfplumber for text and table extraction (superior layout analysis)
        - PyMuPDF for image extraction (excellent image handling)

        Args:
            pdf_path: Path to the source PDF file.
            output_dir: Directory to save the generated Markdown file.
            image_output_dir: Directory to save extracted images.
            public_image_path: URL prefix/path for images in the markdown.
            custom_filename: Optional custom filename for the output markdown file.

        Returns:
            Path to the generated Markdown file.
        """
        logger.info("Converting PDF to Markdown (advanced)", pdf_path=pdf_path)

        # Ensure directories exist
        os.makedirs(image_output_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        filename_base = os.path.splitext(os.path.basename(pdf_path))[0]

        # Open PDF with both libraries
        pdf_plumber = pdfplumber.open(pdf_path)
        pdf_pymupdf = pymupdf.open(pdf_path)

        md_content = ""

        try:
            # Step 0: Collect text from all pages for header/footer detection
            all_pages_text = []
            for page_num, plumber_page in enumerate(pdf_plumber.pages):
                chars = plumber_page.chars
                if chars:
                    all_pages_text.append({
                        "page_num": page_num,
                        "chars": chars,
                        "height": plumber_page.height
                    })
            
            # Detect headers and footers
            header_footer_text = self._detect_headers_footers(all_pages_text)
            
            for page_num, (plumber_page, pymupdf_page) in enumerate(
                zip(pdf_plumber.pages, pdf_pymupdf)
            ):
                logger.debug(f"Processing page {page_num + 1}")

                # Step 1: Extract tables
                tables_md, table_bboxes = self._extract_tables(plumber_page)

                # Step 2: Extract images with positions
                images_md, image_bboxes = self._extract_images(
                    pymupdf_page,
                    page_num,
                    filename_base,
                    image_output_dir,
                    public_image_path,
                )

                # Step 3: Extract text with layout awareness, excluding table and image areas
                text_md = self._extract_text_with_layout(
                    plumber_page, table_bboxes, image_bboxes, header_footer_text
                )

                # Step 4: Merge content in reading order (top to bottom)
                page_content = self._merge_content_by_position(
                    text_md, tables_md, images_md
                )

                md_content += page_content + "\n\n"

        finally:
            pdf_plumber.close()
            pdf_pymupdf.close()

        # Step 5: Post-process markdown for better formatting
        md_content = self._post_process_markdown(md_content)

        # Save Markdown file
        if custom_filename:
            output_filename = custom_filename
            if not output_filename.lower().endswith(".md"):
                output_filename += ".md"
        else:
            output_filename = f"{filename_base}.md"

        output_path = os.path.join(output_dir, output_filename)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info("Conversion complete (advanced)", output_path=output_path)
        return output_path

    def _extract_tables(self, page) -> Tuple[List[Dict], List[Tuple]]:
        """
        Extract tables from a page using pdfplumber.

        Returns:
            Tuple of (list of table markdown dicts with positions, list of table bboxes)
        """
        tables_md = []
        table_bboxes = []

        tables = page.find_tables()

        for table_obj in tables:
            bbox = table_obj.bbox  # (x0, y0, x1, y1)
            table_bboxes.append(bbox)

            # Extract table data
            table_data = table_obj.extract()

            if table_data:
                # Convert to markdown table
                md_table = self._table_to_markdown(table_data)
                tables_md.append(
                    {
                        "type": "table",
                        "content": md_table,
                        "y0": bbox[1],
                        "y1": bbox[3],
                    }
                )

        return tables_md, table_bboxes

    def _table_to_markdown(self, table_data: List[List]) -> str:
        """Convert table data to markdown format."""
        if not table_data or len(table_data) < 1:
            return ""

        # Clean cells (replace None with empty string)
        cleaned_data = []
        for row in table_data:
            cleaned_row = [
                str(cell).strip() if cell is not None else "" for cell in row
            ]
            cleaned_data.append(cleaned_row)

        # Build markdown table
        md_lines = []

        # Header row (first row)
        header = cleaned_data[0]
        md_lines.append("| " + " | ".join(header) + " |")

        # Separator
        md_lines.append("| " + " | ".join(["---"] * len(header)) + " |")

        # Data rows
        for row in cleaned_data[1:]:
            # Pad row if it has fewer columns than header
            while len(row) < len(header):
                row.append("")
            md_lines.append("| " + " | ".join(row[: len(header)]) + " |")

        return "\n".join(md_lines)

    def _extract_images(
        self,
        page,
        page_num: int,
        filename_base: str,
        image_output_dir: str,
        public_image_path: str,
    ) -> Tuple[List[Dict], List[Tuple]]:
        """
        Extract images using PyMuPDF.

        Returns:
            Tuple of (list of image markdown dicts with positions, list of image bboxes)
        """
        images_md = []
        image_bboxes = []

        # Get images from the page
        image_list = page.get_images()

        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]

            try:
                # Get image bbox
                img_rects = page.get_image_rects(xref)
                if not img_rects:
                    continue

                # Use first occurrence bbox
                bbox = img_rects[0]  # pymupdf.Rect
                image_bboxes.append((bbox.x0, bbox.y0, bbox.x1, bbox.y1))

                # Extract image bytes
                base_image = page.parent.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                # Save image
                image_filename = (
                    f"{filename_base}_p{page_num}_img{img_index}.{image_ext}"
                )
                image_path = os.path.join(image_output_dir, image_filename)

                with open(image_path, "wb") as f:
                    f.write(image_bytes)

                # Create markdown link
                md_image = f"![Image]({public_image_path}/{image_filename})"

                images_md.append(
                    {"type": "image", "content": md_image, "y0": bbox.y0, "y1": bbox.y1}
                )

            except Exception as e:
                logger.warning(f"Failed to extract image {img_index}", error=str(e))
                continue

        return images_md, image_bboxes

    def _detect_headers_footers(self, all_pages_text: List[Dict]) -> set:
        """Detect repeated headers and footers across pages.
        
        Returns:
            Set of text strings that appear to be headers or footers
        """
        if len(all_pages_text) < 3:
            return set()  # Need at least 3 pages to reliably detect headers/footers
        
        # Collect text from top and bottom of each page
        top_texts = []  # First 15% of page
        bottom_texts = []  # Last 15% of page
        
        for page_data in all_pages_text:
            chars = page_data["chars"]
            height = page_data["height"]
            
            # Header zone: top 15% of page
            header_zone_limit = height * 0.15
            # Footer zone: bottom 15% of page  
            footer_zone_start = height * 0.85
            
            # Group characters into lines for this page
            header_lines = []
            footer_lines = []
            
            # Simple line grouping by Y position
            current_line = []
            prev_y = None
            
            for char in sorted(chars, key=lambda c: (c["top"], c["x0"])):
                if prev_y is None or abs(char["top"] - prev_y) < 3:
                    current_line.append(char["text"])
                else:
                    line_text = "".join(current_line).strip()
                    if line_text:
                        if prev_y <= header_zone_limit:
                            header_lines.append(line_text)
                        elif prev_y >= footer_zone_start:
                            footer_lines.append(line_text)
                    current_line = [char["text"]]
                prev_y = char["top"]
            
            # Don't forget the last line
            if current_line:
                line_text = "".join(current_line).strip()
                if line_text and prev_y:
                    if prev_y <= header_zone_limit:
                        header_lines.append(line_text)
                    elif prev_y >= footer_zone_start:
                        footer_lines.append(line_text)
            
            top_texts.append(header_lines)
            bottom_texts.append(footer_lines)
        
        # Find text that appears in most pages (>= 50% of pages)
        repeated_threshold = len(all_pages_text) // 2
        headers_footers = set()
        
        # Count occurrences of each text in headers
        from collections import Counter
        all_header_texts = [text for page_headers in top_texts for text in page_headers]
        header_counts = Counter(all_header_texts)
        
        for text, count in header_counts.items():
            if count >= repeated_threshold and len(text) > 3:  # At least 4 characters
                headers_footers.add(text)
        
        # Count occurrences of each text in footers
        all_footer_texts = [text for page_footers in bottom_texts for text in page_footers]
        footer_counts = Counter(all_footer_texts)
        
        for text, count in footer_counts.items():
            if count >= repeated_threshold and len(text) > 3:
                headers_footers.add(text)
        
        logger.info(f"Detected {len(headers_footers)} header/footer texts to exclude")
        return headers_footers

    def _extract_text_with_layout(
        self, page, table_bboxes: List[Tuple], image_bboxes: List[Tuple], header_footer_text: set = None
    ) -> List[Dict]:
        """
        Extract text with layout awareness, excluding table and image areas.

        Returns:
            List of text blocks with metadata and positions
        """
        if header_footer_text is None:
            header_footer_text = set()
        
        text_blocks = []

        # Get all characters with metadata
        chars = page.chars

        if not chars:
            return text_blocks

        # Calculate average font size for relative header detection
        font_sizes = [c["size"] for c in chars]
        avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12

        # Filter out characters in table/image areas
        filtered_chars = []
        for char in chars:
            char_bbox = (char["x0"], char["top"], char["x1"], char["bottom"])
            if not self._is_in_excluded_area(char_bbox, table_bboxes, image_bboxes):
                filtered_chars.append(char)

        if not filtered_chars:
            return text_blocks

        # Group characters into words, then lines, then blocks
        words = self._group_chars_into_words(filtered_chars)
        lines = self._group_words_into_lines(words)
        
        # Filter out header/footer lines
        if header_footer_text:
            filtered_lines = []
            for line in lines:
                line_text = line["text"].strip()
                if line_text not in header_footer_text:
                    filtered_lines.append(line)
            lines = filtered_lines
        
        blocks = self._group_lines_into_blocks(lines, avg_font_size, header_footer_text)

        return blocks

    def _is_in_excluded_area(
        self, char_bbox: Tuple, table_bboxes: List[Tuple], image_bboxes: List[Tuple]
    ) -> bool:
        """Check if a character bbox overlaps with excluded areas."""
        cx0, cy0, cx1, cy1 = char_bbox

        for bbox in table_bboxes + image_bboxes:
            bx0, by0, bx1, by1 = bbox
            # Check overlap
            if cx0 < bx1 and cx1 > bx0 and cy0 < by1 and cy1 > by0:
                return True
        return False

    def _group_chars_into_words(self, chars: List[Dict]) -> List[Dict]:
        """Group characters into words based on spacing."""
        if not chars:
            return []

        words = []
        current_word_chars = [chars[0]]

        for i in range(1, len(chars)):
            prev_char = chars[i - 1]
            curr_char = chars[i]

            # Check if on same line and close together
            vertical_diff = abs(curr_char["top"] - prev_char["top"])
            horizontal_gap = curr_char["x0"] - prev_char["x1"]

            # If close together (< 3 units gap) and same line, add to current word
            if vertical_diff < 2 and horizontal_gap < 3:
                current_word_chars.append(curr_char)
            else:
                # Save current word
                if current_word_chars:
                    words.append(self._chars_to_word(current_word_chars))
                current_word_chars = [curr_char]

        # Don't forget the last word
        if current_word_chars:
            words.append(self._chars_to_word(current_word_chars))

        return words

    def _chars_to_word(self, chars: List[Dict]) -> Dict:
        """Convert a list of chars into a word dict."""
        text = "".join([c["text"] for c in chars])
        return {
            "text": text,
            "x0": min(c["x0"] for c in chars),
            "x1": max(c["x1"] for c in chars),
            "top": min(c["top"] for c in chars),
            "bottom": max(c["bottom"] for c in chars),
            "size": chars[0]["size"],  # Use first char's size
            "fontname": chars[0]["fontname"],
        }

    def _group_words_into_lines(self, words: List[Dict]) -> List[Dict]:
        """Group words into lines based on vertical position."""
        if not words:
            return []

        # Sort words by vertical position, then horizontal
        sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))

        lines = []
        current_line_words = [sorted_words[0]]

        for i in range(1, len(sorted_words)):
            prev_word = sorted_words[i - 1]
            curr_word = sorted_words[i]

            # Check if on same line (similar vertical position)
            vertical_diff = abs(curr_word["top"] - prev_word["top"])

            if vertical_diff < 3:  # Same line
                current_line_words.append(curr_word)
            else:
                # Save current line
                if current_line_words:
                    lines.append(self._words_to_line(current_line_words))
                current_line_words = [curr_word]

        # Don't forget the last line
        if current_line_words:
            lines.append(self._words_to_line(current_line_words))

        return lines

    def _words_to_line(self, words: List[Dict]) -> Dict:
        """Convert a list of words into a line dict."""
        # Sort words by horizontal position for reading order
        sorted_words = sorted(words, key=lambda w: w["x0"])
        text = " ".join([w["text"] for w in sorted_words])

        return {
            "text": text,
            "x0": min(w["x0"] for w in words),
            "x1": max(w["x1"] for w in words),
            "top": min(w["top"] for w in words),
            "bottom": max(w["bottom"] for w in words),
            "size": sorted_words[0]["size"],
            "fontname": sorted_words[0]["fontname"],
        }

    def _group_lines_into_blocks(
        self, lines: List[Dict], avg_font_size: float, header_footer_text: set = None
    ) -> List[Dict]:
        """
        Group lines into text blocks and detect formatting.

        Returns blocks with markdown formatting applied.
        """
        if not lines:
            return []
        
        if header_footer_text is None:
            header_footer_text = set()
        
        # Step 1: Merge separated section numbers with their following text
        merged_lines = self._merge_section_numbers(lines)

        blocks = []
        i = 0
        
        while i < len(merged_lines):
            line = merged_lines[i]
            text = line["text"].strip()
            if not text:
                i += 1
                continue

            # Detect formatting for this line
            is_header, header_level = self._detect_header(
                line, avg_font_size, len(text)
            )
            is_bold = self._is_bold(line["fontname"])
            is_italic = self._is_italic(line["fontname"])
            is_list, list_marker, indent_level = self._detect_list_type(text)

            # Headers and lists are standalone blocks
            if is_header and header_level:
                md_text = "#" * header_level + " " + text
                blocks.append({
                    "type": "text",
                    "content": md_text,
                    "y0": line["top"],
                    "y1": line["bottom"],
                })
                i += 1
            elif is_list:
                # Format as list item with proper indentation
                # Collect the full list item including continuation lines
                list_item_lines = [text]
                y0 = line["top"]
                y1 = line["bottom"]
                i += 1
                
                # Look ahead for continuation lines (lines that don't start with a list marker)
                while i < len(merged_lines):
                    next_line = merged_lines[i]
                    next_text = next_line["text"].strip()
                    if not next_text:
                        i += 1
                        continue
                    
                    # Skip if this line is a header/footer
                    if next_text in header_footer_text:
                        i += 1
                        continue
                    
                    next_is_header, _ = self._detect_header(next_line, avg_font_size, len(next_text))
                    next_is_list, _, _ = self._detect_list_type(next_text)
                    
                    # Stop if we hit a header or another list item
                    if next_is_header or next_is_list:
                        break
                    
                    # This is a continuation line - add it to the list item
                    list_item_lines.append(next_text)
                    y1 = next_line["bottom"]
                    i += 1
                
                # Join all lines of the list item
                full_list_text = " ".join(list_item_lines)
                
                # Now clean the marker from the full text
                indent = "  " * indent_level
                cleaned_text = re.sub(r'^[•·◦▪▫–\-\*]\s+', '', full_list_text)
                cleaned_text = re.sub(r'^\([ivxlcdm]+\)\s+', '', cleaned_text, flags=re.IGNORECASE)
                cleaned_text = re.sub(r'^\([a-z]\)\s+', '', cleaned_text)
                cleaned_text = re.sub(r'^[a-z]\)\s+', '', cleaned_text)
                cleaned_text = re.sub(r'^\d+[\\.]\s+', '', cleaned_text)
                
                md_text = f"{indent}{list_marker} {cleaned_text}"
                blocks.append({
                    "type": "list",
                    "content": md_text,
                    "y0": y0,
                    "y1": y1,
                })
            else:
                # Regular text - group consecutive lines into a paragraph
                paragraph_lines = [text]
                y0 = line["top"]
                y1 = line["bottom"]
                i += 1
                
                # Look ahead and group consecutive non-header, non-list lines
                while i < len(merged_lines):
                    next_line = merged_lines[i]
                    next_text = next_line["text"].strip()
                    if not next_text:
                        i += 1
                        continue
                    
                    # Skip if this line is a header/footer
                    if next_text in header_footer_text:
                        i += 1
                        continue
                    
                    next_is_header, _ = self._detect_header(next_line, avg_font_size, len(next_text))
                    next_is_list, _, _ = self._detect_list_type(next_text)
                    
                    # Stop if we hit a header or list
                    if next_is_header or next_is_list:
                        break
                    
                    # Add this line to the paragraph
                    paragraph_lines.append(next_text)
                    y1 = next_line["bottom"]
                    i += 1
                
                # Join paragraph lines with spaces
                paragraph_text = " ".join(paragraph_lines)
                
                # Apply inline formatting
                if is_bold:
                    paragraph_text = f"**{paragraph_text}**"
                elif is_italic:
                    paragraph_text = f"*{paragraph_text}*"
                
                blocks.append({
                    "type": "text",
                    "content": paragraph_text,
                    "y0": y0,
                    "y1": y1,
                })

        return blocks

    def _merge_section_numbers(self, lines: List[Dict]) -> List[Dict]:
        """
        Merge lines where section numbers are separated from their text.
        
        Example:
            ["20.", "PUBLICITY AND USE OF NAMES"] -> ["20. PUBLICITY AND USE OF NAMES"]
        """
        if not lines:
            return lines
        
        merged = []
        i = 0
        
        while i < len(lines):
            current_line = lines[i]
            current_text = current_line["text"].strip()
            
            # Check if this line is just a section number
            if self.section_number_pattern.match(current_text):
                # Check if there's a next line to merge with
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    
                    # Merge the section number with the next line
                    merged_text = current_text + " " + next_line["text"].strip()
                    
                    merged_line = {
                        "text": merged_text,
                        "x0": min(current_line["x0"], next_line["x0"]),
                        "x1": max(current_line["x1"], next_line["x1"]),
                        "top": current_line["top"],
                        "bottom": next_line["bottom"],
                        "size": max(current_line["size"], next_line["size"]),  # Use larger size
                        "fontname": next_line["fontname"],  # Use text's font, not number's
                    }
                    merged.append(merged_line)
                    i += 2  # Skip both lines
                    continue
            
            # Not a section number or nothing to merge with
            merged.append(current_line)
            i += 1
        
        return merged

    def _detect_header(
        self, line: Dict, avg_font_size: float, text_length: int
    ) -> Tuple[bool, Optional[int]]:
        """
        Detect if a line is a header using multiple signals.

        Returns:
            Tuple of (is_header, header_level)
        """
        text = line["text"].strip()
        size_ratio = line["size"] / avg_font_size
        fontname = line["fontname"].lower()
        
        # Signal 0: Check for numbered section patterns (strongest signal)
        numbered_match = self.numbered_header_pattern.match(text)
        if numbered_match:
            section_num = numbered_match.group(1)
            # Determine level by number of dots
            dot_count = section_num.count('.')
            
            if dot_count == 0:  # Just a number (e.g., "20")
                return True, 1  # Top level
            elif dot_count == 1:  # e.g., "20." or "1"
                return True, 1
            elif dot_count == 2:  # e.g., "1.1."
                return True, 2
            elif dot_count == 3:  # e.g., "1.1.1."
                return True, 3
            else:  # e.g., "1.1.1.1."
                return True, 3  # Max at H3

        # Signal 1: Font size (relative to average)
        size_score = 0
        if size_ratio > self.header_size_threshold_large:
            size_score = 3  # H1
        elif size_ratio > self.header_size_threshold_medium:
            size_score = 2  # H2
        elif size_ratio > self.header_size_threshold_small:
            size_score = 1  # H3

        # Signal 2: Font weight (bold often indicates headers)
        is_bold = "bold" in fontname

        # Signal 3: Text length (headers usually shorter)
        is_short = text_length < 100

        # Combine signals
        if size_score >= 2:
            return True, min(size_score, 3)
        elif size_score == 1 and (is_bold or is_short):
            return True, 3
        elif is_bold and is_short and text_length < 50:
            return True, 3

        return False, None

    def _is_bold(self, fontname: str) -> bool:
        """Check if font indicates bold text."""
        return "bold" in fontname.lower()

    def _is_italic(self, fontname: str) -> bool:
        """Check if font indicates italic text."""
        return "italic" in fontname.lower() or "oblique" in fontname.lower()

    def _detect_list_type(self, text: str) -> tuple[bool, str, int]:
        """Detect if text is a list item and determine its type and indent level.
        
        Returns:
            (is_list, list_marker, indent_level)
            - is_list: whether this is a list item
            - list_marker: the markdown marker to use (preserves original for roman/letters)
            - indent_level: 0 for top-level, 1 for nested, 2 for double-nested, etc.
        """
        text = text.strip()
        if len(text) < 2:
            return False, "", 0

        # Bullet points - convert to dash
        if text[0] in ["•", "·", "◦", "▪", "▫"]:
            return True, "-", 0
        
        # Dash bullets - keep as is
        if text[0] in ["–", "-", "*"] and len(text) > 1 and text[1] == " ":
            return True, "-", 0

        # Roman numerals in parentheses: (i), (ii), (iii), (iv), etc.
        # PRESERVE the original marker for clarity
        roman_match = re.match(r'^\(([ivxlcdm]+)\)\s+', text, re.IGNORECASE)
        if roman_match:
            original_marker = f"({roman_match.group(1)})"  # Keep as (i), (ii), etc.
            return True, original_marker, 1  # Still nested (indent level 1)
        
        # Letters in parentheses: (a), (b), (c) or a), b), c)
        # PRESERVE the original marker
        letter_match = re.match(r'^(\([a-z]\)|[a-z]\))\s+', text)
        if letter_match:
            original_marker = letter_match.group(1)  # Keep as (a), a), etc.
            return True, original_marker, 2  # Double-nested (indent level 2)
        
        # Numbered lists: 1., 2., 3.
        number_match = re.match(r'^(\d+)\.\s+', text)
        if number_match:
            num = number_match.group(1)
            return True, f"{num}.", 0
        
        # Numbered with closing paren: 1), 2), 3)
        number_paren_match = re.match(r'^(\d+)\)\s+', text)
        if number_paren_match:
            num = number_paren_match.group(1)
            return True, f"{num})", 0  # Preserve the paren style

        return False, "", 0
    
    def _is_list_item(self, text: str) -> bool:
        """Check if text appears to be a list item (for backward compatibility)."""
        is_list, _, _ = self._detect_list_type(text)
        return is_list

    def _merge_content_by_position(
        self, text_blocks: List[Dict], tables: List[Dict], images: List[Dict]
    ) -> str:
        """
        Merge all content blocks in reading order (top to bottom).
        """
        all_blocks = text_blocks + tables + images

        # Sort by vertical position
        all_blocks.sort(key=lambda b: b["y0"])

        # Build markdown
        md_lines = []
        prev_type = None

        for block in all_blocks:
            content = block["content"]

            # Add spacing between blocks for better readability
            if prev_type is not None:
                # Always add blank line between different types
                if prev_type != block["type"]:
                    md_lines.append("")  
                # Add blank line between text blocks (paragraphs)
                elif block["type"] == "text":
                    md_lines.append("")
                # Add blank line between list items (so non-standard markers like (i) render separately)
                elif block["type"] == "list":
                    md_lines.append("")

            md_lines.append(content)
            prev_type = block["type"]

        return "\n".join(md_lines)

    def _post_process_markdown(self, md_content: str) -> str:
        """
        Post-process markdown to clean up formatting.
        """
        lines = md_content.split("\n")
        processed_lines = []

        prev_line = ""
        for line in lines:
            stripped = line.strip()

            # Remove excessive blank lines (max 2 consecutive)
            if not stripped:
                if prev_line.strip():  # Previous was not blank
                    processed_lines.append("")
                elif len(processed_lines) > 0 and processed_lines[-1] != "":
                    processed_lines.append("")
                # Otherwise skip this blank line
                prev_line = line
                continue

            processed_lines.append(line)
            prev_line = line

        # Join and clean up
        result = "\n".join(processed_lines)

        # Remove more than 2 consecutive newlines
        import re

        result = re.sub(r"\n{3,}", "\n\n", result)

        return result.strip()


_converter_service: DocumentConverter | None = None


def get_converter_service():
    global _converter_service
    if _converter_service is None:
        _converter_service = DocumentConverter()
    return _converter_service
