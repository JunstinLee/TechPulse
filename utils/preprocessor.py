import re

class TextCleaner:
    """Provides basic regex filtering and text cleaning functionality"""

    @staticmethod
    def remove_images(text: str) -> str:
        """Remove all image links ![]() and HTML <img> tags"""
        if not text:
            return ""
        # Match Markdown images: ![alt](url)
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        # Match HTML img tags: <img ...>
        text = re.sub(r'<img\s+[^>]*>', '', text)
        return text

    @staticmethod
    def remove_badges(text: str) -> str:
        """Remove SVG status icons (Badges)"""
        if not text:
            return ""
        # Match Badge links in Markdown: [![...](...)](...)
        text = re.sub(r'\[\!\[.*?\]\(.*?\)\]\(.*?\)', '', text)
        # Match standalone Badge images: ![](https://img.shields.io/...)
        text = re.sub(r'\!\[.*?\]\(https?://img\.shields\.io/.*?\)', '', text)
        # Match common Badge HTML
        text = re.sub(r'<a\s+href=.*?><img\s+src="https?://img\.shields\.io/.*?".*?></a>', '', text)
        return text

    @staticmethod
    def remove_toc(text: str) -> str:
        """Remove Table of Contents"""
        if not text:
            return ""
        # Match common TOC markers
        text = re.sub(r'(?i)#+\s*table\s*of\s*contents.*?\n', '', text)
        # Simple handling: if a line consists entirely of links and list markers, it's likely a TOC
        lines = text.split('\n')
        new_lines = []
        for line in lines:
            if re.match(r'^\s*[\-\*\+]\s*\[.*?\]\(#.*?\)\s*$', line):
                continue
            new_lines.append(line)
        return '\n'.join(new_lines)

    @staticmethod
    def clean_full(text: str) -> str:
        """Execute full cleaning combination"""
        text = TextCleaner.remove_images(text)
        text = TextCleaner.remove_badges(text)
        text = TextCleaner.remove_toc(text)
        # Remove HTML comments
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        # Compress extra blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

class ContentExtractor:
    """Identify core sections (e.g., Features, Intro)"""
    
    @staticmethod
    def extract_core_sections(text: str) -> str:
        """Attempt to extract core sections, return original text if not identified"""
        if not text:
            return ""
        
        # Find common core section titles
        core_patterns = [
            r'(?i)#+\s*(?:Introduction|Intro|About|What is).*?\n',
            r'(?i)#+\s*(?:Features|Key Features|Highlights|Core Functions).*?\n',
            r'(?i)#+\s*(?:Usage|Quick Start|Getting Started).*?\n'
        ]
        
        # If text is too short, return as is
        if len(text) < 1000:
            return text
            
        # Simple section detection logic (split by headings)
        sections = re.split(r'(^#+\s+.*$)', text, flags=re.MULTILINE)
        
        core_content = []
        important_found = False
        
        for i in range(1, len(sections), 2):
            title = sections[i]
            content = sections[i+1] if i+1 < len(sections) else ""
            
            # Check if this is a core section
            is_core = False
            for pattern in core_patterns:
                if re.match(pattern, title):
                    is_core = True
                    important_found = True
                    break
            
            if is_core:
                core_content.append(title + content)
        
        if important_found:
            return "\n\n".join(core_content)
        
        return text  # Return full text if no core sections found

class TokenManager:
    """Handle text truncation to ensure compliance with AI context limits"""
    
    @staticmethod
    def smart_truncate(text: str, max_chars: int = 3000) -> str:
        """Smart truncation: prioritize preserving core content"""
        if len(text) <= max_chars:
            return text
            
        # First try to reduce by extracting core sections
        core = ContentExtractor.extract_core_sections(text)
        if len(core) > 500 and len(core) <= max_chars:
            return core
            
        # If all else fails, brute force truncation
        return text[:max_chars] + "\n\n[...content truncated...]"
