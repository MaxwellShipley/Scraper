import requests
from bs4 import BeautifulSoup
import json 
import time
from urllib.parse import urljoin, urlparse, unquote

# --- Configuration ---
OUTPUT_JSON_FILE = "user_profiles.json" 
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/124.0.0.0',
]
CURRENT_USER_AGENT = USER_AGENTS[0]

BASE_REQUEST_HEADERS = {
    'User-Agent': CURRENT_USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'DNT': '1',
}

# This list defines the expected keys for each profile dictionary.
# It helps ensure consistency in the JSON output.
PROFILE_DATA_KEYS = [
    'Profile URL', 'Display Name', 'Headline', 'First Name', 'Pronouns',
    'Current Title/Role', 'About', 'Website',
    'Email Address', 'Connect Link',
    'Most Recent Work', 'Publications/Case Studies', 'Work Showcase Files',
    'Expertise Areas', 'Certifications',
    'Testimonials'
]

session = requests.Session()
session.headers.update(BASE_REQUEST_HEADERS)

# --- Helper Functions ---
def get_soup(url, referer=None):
    print(f"Fetching URL: {url}")
    headers = session.headers.copy()
    if referer:
        headers['Referer'] = referer
    try:
        response = session.get(url, headers=headers, timeout=20)
        response.raise_for_status()

        print(f"DEBUG: Initial response.encoding: {response.encoding}")
        print(f"DEBUG: Initial response.apparent_encoding: {response.apparent_encoding}")

        if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
            if response.apparent_encoding:
                print(f"DEBUG: Setting response.encoding to apparent_encoding: {response.apparent_encoding}")
                response.encoding = response.apparent_encoding
            else:
                print(f"DEBUG: Apparent encoding also None, defaulting to 'utf-8'.")
                response.encoding = 'utf-8'
        
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        
        return soup
    except requests.exceptions.Timeout:
        print(f"Error fetching URL {url}: Request timed out")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return None
    except Exception as ex:
        print(f"An unexpected error occurred in get_soup for {url}: {ex}")
        return None

def get_field_value_from_soup(soup_obj, data_key, get_html_content=False, context_name=""):
    field_div_to_search = None

    if soup_obj and soup_obj.name == 'div' and soup_obj.get('class') and 'um-field' in soup_obj.get('class') and soup_obj.get('data-key') == data_key:
        field_div_to_search = soup_obj
    elif soup_obj:
        field_div_to_search = soup_obj.find('div', class_='um-field', attrs={'data-key': data_key})
    else:
        print(f"DEBUG ({context_name}): soup_obj is None for data_key='{data_key}'")
        return None, None

    if field_div_to_search:
        value_div = field_div_to_search.find('div', class_='um-field-value')
        if value_div:
            if get_html_content:
                return value_div.decode_contents().strip(), None
            if value_div.find('a'):
                link = value_div.find('a')
                text = link.text.strip()
                href = link.get('href', '')
                return text, href
            return value_div.text.strip(), None
        else:
            print(f"DEBUG ({context_name}): WARNING: Found field_div for '{data_key}', but NO value_div inside it.")
            return None, None
    else:
        return None, None

def get_tab_url(base_user_url, tab_key):
    if not base_user_url.endswith('/'):
        base_user_url += '/'
    return f"{base_user_url}?profiletab={tab_key}"

# --- Core Scraping Functions ---
def scrape_about_section(main_soup, base_url):
    about_data = {'Profile URL': base_url}
    context_name = "About"
    print(f"--- Starting scrape_about_section for {base_url} ---")

    if not main_soup:
        print(f"DEBUG ({context_name}): main_soup is None. Cannot scrape About section.")
        try:
            with open("debug_about_page.html", "w", encoding="utf-8") as f:
                f.write("main_soup was None" if not main_soup else main_soup.prettify())
            print(f"DEBUG ({context_name}): Saved HTML (or status) to debug_about_page.html")
        except Exception as e:
            print(f"DEBUG ({context_name}): Error saving HTML to debug_about_page.html: {e}")
        return about_data

    try:
        with open("debug_about_page.html", "w", encoding="utf-8") as f:
            f.write(main_soup.prettify())
        print(f"DEBUG ({context_name}): Saved full HTML to debug_about_page.html")
    except Exception as e:
        print(f"DEBUG ({context_name}): Error saving HTML to debug_about_page.html: {e}")

    profile_main_container = main_soup.find('div', class_='um-profile')
    if not profile_main_container:
        print(f"DEBUG ({context_name}): FAILED to find 'div.um-profile'. Using main_soup as search context.")
        profile_main_container = main_soup
    else:
        print(f"DEBUG ({context_name}): Found 'div.um-profile'.")

    name_headline_area = profile_main_container.find('div', class_='um-profile-meta')
    if not name_headline_area:
        name_headline_area = profile_main_container.find('div', class_='um-profile-one-content')
    
    if name_headline_area:
        print(f"DEBUG ({context_name}): Found potential name/headline area.")
        name_element = name_headline_area.find('div', class_='um-name')
        if name_element and name_element.find('a'):
            about_data['Display Name'] = name_element.find('a').text.strip()
        headline_element = name_headline_area.find('div', class_='um-meta')
        if headline_element and headline_element.find('p'):
            about_data['Headline'] = headline_element.find('p').text.strip()
    else:
        print(f"DEBUG ({context_name}): FAILED to find 'um-profile-meta' or 'um-profile-one-content' for name/headline.")

    meet_me_content_area = profile_main_container.find('div', class_='um-profile-body')
    search_context_for_fields = meet_me_content_area if meet_me_content_area else profile_main_container

    first_name_val, _ = get_field_value_from_soup(search_context_for_fields, 'first_name', context_name=context_name)
    if first_name_val: about_data['First Name'] = first_name_val

    pronouns_val, _ = get_field_value_from_soup(search_context_for_fields, 'pronouns', context_name=context_name)
    if pronouns_val: about_data['Pronouns'] = pronouns_val

    title_role_val, _ = get_field_value_from_soup(search_context_for_fields, 'title_role', context_name=context_name)
    if title_role_val: about_data['Current Title/Role'] = title_role_val

    about_html_content, _ = get_field_value_from_soup(search_context_for_fields, 'about', get_html_content=True, context_name=context_name)
    if about_html_content:
        about_soup_inner = BeautifulSoup(about_html_content, 'html.parser')
        about_data['About'] = "\n".join([p.text.strip() for p in about_soup_inner.find_all('p')])

    _, website_link = get_field_value_from_soup(search_context_for_fields, 'user_url', context_name=context_name)
    if website_link: 
        about_data['Website'] = website_link

    email_val, _ = get_field_value_from_soup(search_context_for_fields, 'user_email', context_name=context_name)
    if email_val: about_data['Email Address'] = email_val
    
    print(f"--- Finished scrape_about_section. ---")
    return about_data

def scrape_tab_content(tab_url_full, tab_name_key, referer_url):
    tab_data = {}
    context_name = f"Tab-{tab_name_key}"
    print(f"--- Starting scrape_tab_content for {tab_name_key} from {tab_url_full} ---")

    soup = get_soup(tab_url_full, referer=referer_url)
    if not soup:
        print(f"DEBUG ({context_name}): soup is None. Cannot scrape this tab.")
        return tab_data

    try:
        with open(f"debug_{tab_name_key}_page.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        print(f"DEBUG ({context_name}): Saved full HTML to debug_{tab_name_key}_page.html")
    except Exception as e:
        print(f"DEBUG ({context_name}): Error saving HTML to debug_{tab_name_key}_page.html: {e}")

    content_area = soup.find('div', class_=f'um-profile-body {tab_name_key}')
    if not content_area: content_area = soup.find('div', class_=tab_name_key)
    if not content_area: content_area = soup.find('div', class_='um-profile-body') 
    if not content_area:
        print(f"DEBUG ({context_name}): FAILED to find main content_area. Using entire tab page 'soup'.")
        content_area = soup
    else:
        print(f"DEBUG ({context_name}): Found content_area.")

    if tab_name_key == "my-work":
        recent_work_html, _ = get_field_value_from_soup(content_area, 'recent_work2', get_html_content=True, context_name=context_name)
        if recent_work_html:
            recent_work_soup = BeautifulSoup(recent_work_html, 'html.parser')
            recent_work_items = [p.text.strip() for p in recent_work_soup.find_all('p') if p.text.strip()]
            tab_data['Most Recent Work'] = "\n\n".join(recent_work_items) if recent_work_items else ""

        publications_html, _ = get_field_value_from_soup(content_area, 'publications', get_html_content=True, context_name=context_name)
        if publications_html:
            publications_soup = BeautifulSoup(publications_html, 'html.parser')
            publication_items = [p.text.strip() for p in publications_soup.find_all('p') if p.text.strip()]
            tab_data['Publications/Case Studies'] = "\n\n".join(publication_items) if publication_items else ""

        showcase_field = content_area.find('div', class_='um-field', attrs={'data-key': 'showcase'})
        if showcase_field:
            file_items = []
            for file_div in showcase_field.find_all('div', class_='um-single-file-preview'):
                link_tag = file_div.find('a')
                filename_tag = file_div.find('span', class_='filename')
                if link_tag and filename_tag:
                    href = link_tag.get('href')
                    clean_filename = filename_tag.text.strip()
                    try:
                        parsed_href = urlparse(href)
                        path_filename = unquote(parsed_href.path.split('/')[-1])
                        if any(path_filename.lower().endswith(ext) for ext in ['.pdf', '.doc', '.docx', '.txt', '.jpg', '.png']):
                           clean_filename = path_filename
                    except:
                        pass
                    full_url = urljoin(tab_url_full, href) if href else "N/A"
                    file_items.append(f"Filename: {clean_filename}, Link: {full_url}")
            tab_data['Work Showcase Files'] = "; ".join(file_items) if file_items else ""

    elif tab_name_key == "expertise":
        expertise_text_val, _ = get_field_value_from_soup(content_area, 'expertise_text', context_name=context_name)
        if expertise_text_val:
            tab_data['Expertise Areas'] = expertise_text_val

        certifications_html, _ = get_field_value_from_soup(content_area, 'certifications', get_html_content=True, context_name=context_name)
        if certifications_html:
            cert_soup = BeautifulSoup(certifications_html, 'html.parser')
            cert_items = []
            for p_tag in cert_soup.find_all('p'):
                for br in p_tag.find_all('br'):
                    br.replace_with("\n")
                lines = [line.strip() for line in p_tag.text.split('\n') if line.strip()]
                cert_items.extend(lines)
            tab_data['Certifications'] = "; ".join(cert_items) if cert_items else ""

    elif tab_name_key == "testimonials":
        testimonials_list = []
        testimonial_fields = content_area.find_all('div', class_='um-field', attrs={'data-key': True})
        for field in testimonial_fields:
            data_key_val = field.get('data-key')
            if data_key_val and data_key_val.startswith('Testimonial'):
                label_div = field.find('div', class_='um-field-label')
                label = label_div.find('label').text.strip() if label_div and label_div.find('label') else data_key_val
                value_html, _ = get_field_value_from_soup(field, data_key_val, get_html_content=True, context_name=f"{context_name}-{data_key_val}")
                if value_html:
                    value_soup = BeautifulSoup(value_html, 'html.parser')
                    testimonial_parts = [p.text.strip() for p in value_soup.find_all('p') if p.text.strip()]
                    if testimonial_parts:
                        text = " ".join(testimonial_parts[:-1]) if len(testimonial_parts) > 1 else testimonial_parts[0]
                        author = testimonial_parts[-1] if len(testimonial_parts) > 1 else "N/A"
                        if testimonial_parts[-1].strip().startswith('-'):
                            author = testimonial_parts[-1].strip()
                            text = " ".join(testimonial_parts[:-1]).strip()
                        else:
                            text = " ".join(testimonial_parts).strip()
                            author = "N/A"
                        testimonials_list.append(f"{label}: '{text}' - Author: {author}")
        tab_data['Testimonials'] = "\n\n".join(testimonials_list) if testimonials_list else ""

    print(f"--- Finished scrape_tab_content for {tab_name_key}. ---")
    return tab_data

# --- Main Script Logic ---
def scrape_profile(user_profile_url):
    print(f"Scraping profile: {user_profile_url}")
    # Initialize profile_data with all expected keys having an empty string or None value
    profile_data = {key: "" for key in PROFILE_DATA_KEYS}
    profile_data['Profile URL'] = user_profile_url # Set this initially

    main_soup = get_soup(user_profile_url, referer='https://www.google.com/')
    if not main_soup:
        print(f"CRITICAL: Could not retrieve or parse the main profile page: {user_profile_url}")
        profile_data['Connect Link'] = get_tab_url(user_profile_url, "connect")
        # Return the initialized dict with URL and Connect Link
        return profile_data


    about_info = scrape_about_section(main_soup, user_profile_url)
    profile_data.update(about_info) # Update with any found 'about' info
    time.sleep(1)

    work_tab_key = "my-work"
    work_url = get_tab_url(user_profile_url, work_tab_key)
    work_data = scrape_tab_content(work_url, work_tab_key, referer_url=user_profile_url)
    profile_data.update(work_data)
    time.sleep(1)

    expertise_tab_key = "expertise"
    expertise_url = get_tab_url(user_profile_url, expertise_tab_key)
    expertise_data = scrape_tab_content(expertise_url, expertise_tab_key, referer_url=user_profile_url)
    profile_data.update(expertise_data)
    time.sleep(1)

    testimonials_tab_key = "testimonials" # Assuming this is the correct key based on CSV_FIELDNAMES
    testimonials_url = get_tab_url(user_profile_url, testimonials_tab_key)
    testimonials_data = scrape_tab_content(testimonials_url, testimonials_tab_key, referer_url=user_profile_url)
    profile_data.update(testimonials_data)
    time.sleep(1)
    
    profile_data['Connect Link'] = get_tab_url(user_profile_url, "connect")

    # Ensure all keys from PROFILE_DATA_KEYS are present
    # This step is now handled by initializing profile_data with all keys.
    # We just need to ensure the final dictionary uses profile_data as its base.
    # final_profile_dict = {key: profile_data.get(key, "") for key in PROFILE_DATA_KEYS}

    return profile_data # This is already a dictionary structured as desired

def main():
    user_urls_to_scrape = [
        "https://loommas.com/user/anca.castillo/",
        "https://loommas.com/user/cary.lopez/",
        "https://loommas.com/user/col.jason.%22toga%22.trew%2c.phd.%28usaf%2c.retired%29/",
        "https://loommas.com/user/rob.razzante%2c.phd/",
        "https://loommas.com/user/sarah.tracy/",
        "https://loommas.com/user/nicole.schlagheck/"
    ]

    all_scraped_data = []
    for i, user_url in enumerate(user_urls_to_scrape):
        print("=" * 60)
        scraped_profile_dict = scrape_profile(user_url)
        all_scraped_data.append(scraped_profile_dict) # Add the dictionary to the list
        print(f"Finished processing: {user_url}")
        if len(user_urls_to_scrape) > 1 and user_url != user_urls_to_scrape[-1]:
            print("Pausing for 2 seconds before next profile...")
            time.sleep(2)

    if not all_scraped_data:
        print("No data was scraped. Exiting JSON write.")
        return

    print(f"\nWriting {len(all_scraped_data)} profile(s) to {OUTPUT_JSON_FILE}")
    try:
        with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as jsonfile:
            json.dump(all_scraped_data, jsonfile, indent=4, ensure_ascii=False) # Save list of dicts as JSON array
        print(f"Successfully saved data to {OUTPUT_JSON_FILE}")
    except IOError as e:
        print(f"Error writing JSON file: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during JSON writing: {e}")

if __name__ == "__main__":
    main()