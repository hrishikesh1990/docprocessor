import re
import fitz

class LinkExtractor:
    @staticmethod
    def extract_all_links(pdf_bytes, extracted_text):
        """Extract both annotation and text-based links from PDF"""
        links = {
            'text_links': set(),
            'annotation_links': set(),
            'linkedin_links': set(),
            'github_links': set(),
            'stackoverflow_links': set(),
            'email_links': set(),
            'web_links': set()
        }

        # Extract links from PDF annotations
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            # Get annotation (clickable) links
            for link in page.get_links():
                if 'uri' in link:  # Check if it's a URI link
                    uri = link['uri']
                    if uri:
                        links['annotation_links'].add(uri)
                        # Categorize the annotation link
                        if 'linkedin.com' in uri.lower():
                            links['linkedin_links'].add(uri)
                        elif 'github.com' in uri.lower():
                            links['github_links'].add(uri)
                        elif 'stackoverflow.com' in uri.lower():
                            links['stackoverflow_links'].add(uri)
                        else:
                            links['web_links'].add(uri)

            # Get text-based links
            urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', extracted_text)
            for url in urls:
                if url not in links['annotation_links']:  # Avoid duplicates
                    links['text_links'].add(url)
                    # Categorize the text link
                    if 'linkedin.com' in url.lower():
                        links['linkedin_links'].add(url)
                    elif 'github.com' in url.lower():
                        links['github_links'].add(url)
                    elif 'stackoverflow.com' in url.lower():
                        links['stackoverflow_links'].add(url)
                    else:
                        links['web_links'].add(url)

        # Get email addresses
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', extracted_text)
        links['email_links'].update(emails)

        # Convert sets to lists for JSON serialization
        return {k: list(v) for k, v in links.items()}