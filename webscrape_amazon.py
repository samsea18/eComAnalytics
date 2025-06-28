import os
import time
import json
import csv
import random
import logging
from datetime import datetime
from typing import List, Dict, Any
import certifi
import yaml
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def random_sleep(min_sec: float = 5, max_sec: float = 10) -> None:
    duration = random.uniform(min_sec, max_sec)
    logger.info(f"Sleeping for {duration:.2f} seconds...")
    time.sleep(duration)


def load_config(path: str = "config/config.yaml") -> Dict[str, Any]:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def setup_driver() -> uc.Chrome:
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    )
    # options.add_argument("--headless")
    return uc.Chrome(options=options)


def click_continue_shopping(driver: uc.Chrome) -> None:
    try:
        btn = driver.find_element(By.XPATH, "//button[normalize-space(text())='Continue shopping']")
        btn.click()
        logger.info("Clicked 'Continue Shopping'")
        random_sleep(2, 6)
    except Exception:
        logger.info("No 'Continue Shopping' button found")


def apply_gender_filters(driver: uc.Chrome, gender_filters: List[str]) -> None:
    try:
        logger.info(f"Applying Gender filters: {', '.join(gender_filters)}")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "p_n_feature_twenty-eight_browse-bin-title"))
        )

        gender_section = driver.find_element(By.ID, "p_n_feature_twenty-eight_browse-bin-title")
        driver.execute_script("arguments[0].scrollIntoView();", gender_section)
        random_sleep(1, 5)

        for gender in gender_filters:
            gender_links = driver.find_elements(
                By.XPATH,
                f"//a[contains(@aria-label, 'Apply the filter') and contains(@aria-label, '{gender}')]"
            )
            if gender_links:
                href = gender_links[0].get_attribute("href")
                driver.get(href)
                logger.info(f"Clicked filter: {gender}")
                random_sleep(3, 6)
    except Exception as e:
        logger.warning(f"Gender filters not found or clickable: {e}")


def scrape_products_on_page(driver: uc.Chrome) -> List[Dict[str, str]]:
    searched_data = []
    products = driver.find_elements(By.XPATH, "//div[@data-asin and @data-asin != '']")
    logger.info(f"Found {len(products)} products on page")

    for product in products:
        try:
            asin = product.get_attribute("data-asin")

            try:
                brand = product.find_element(
                    By.XPATH,
                    ".//h2[@class='a-size-mini s-line-clamp-1']/span[contains(@class, 'a-size-base-plus')]"
                ).text
            except Exception:
                brand = ""

            try:
                title = product.find_element(By.XPATH, ".//h2[@aria-label]/span").text
            except Exception:
                title = ""

            try:
                link = product.find_element(By.TAG_NAME, "a").get_attribute("href")
            except Exception:
                link = ""

            try:
                price_whole = product.find_element(By.CLASS_NAME, "a-price-whole").text
                price_frac = product.find_element(By.CLASS_NAME, "a-price-fraction").text
                price = f"S${price_whole}.{price_frac}"
            except Exception:
                price = "N/A"

            try:
                rating = product.find_element(By.XPATH, ".//span[contains(@class,'a-icon-alt')]").get_attribute("innerText")
            except Exception:
                rating = ""

            try:
                product.find_element(By.XPATH, ".//span[contains(text(),'Sponsored')]")
                sponsored = "Yes"
            except Exception:
                sponsored = "No"

            searched_data.append({
                "prodTypeID": asin,
                "brand": brand,
                "title": title,
                "price": price,
                "rating": rating,
                "sponsored": sponsored,
                "link": link
            })

        except Exception as e:
            logger.warning(f"Skipping a product due to error: {e}")

    return searched_data


def navigate_next_page(driver: uc.Chrome) -> bool:
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        random_sleep(2, 5)
        next_btn = driver.find_element(By.XPATH, "//a[contains(@class, 's-pagination-next') and contains(text(), 'Next')]")
        driver.execute_script("arguments[0].scrollIntoView();", next_btn)
        next_btn.click()
        logger.info("Navigated to next page")
        random_sleep()
        return True
    except Exception as e:
        logger.warning(f"No next page button found or last page reached: {e}")
        return False


def save_data(data: List[Dict[str, str]], search_term: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    slug = search_term.lower().replace(" ", "_")
    json_path = f"data/{slug}_{timestamp}.json"
    csv_path = f"data/{slug}_{timestamp}.csv"

    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(data, jf, ensure_ascii=False, indent=2)

    with open(csv_path, "w", newline='', encoding="utf-8") as cf:
        writer = csv.DictWriter(cf, fieldnames=["prodTypeID", "brand", "title", "price", "rating", "sponsored", "link"])
        writer.writeheader()
        writer.writerows(data)

    logger.info(f"Saved {len(data)} items to {json_path} and {csv_path}")


def main() -> None:
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.makedirs("data", exist_ok=True)

    config = load_config()
    search_term = config["search_term"]
    website_url = config["website_url"]
    pages_to_scrape = config["pages_to_scrape"]
    gender_filters = config.get("gender_filters", [])

    driver = setup_driver()
    searched_data: List[Dict[str, str]] = []

    try:
        driver.get(website_url)
        random_sleep(3, 6)

        click_continue_shopping(driver)

        # Search for term
        search_box = driver.find_element(By.ID, "twotabsearchtextbox")
        search_box.send_keys(search_term)
        search_box.send_keys(Keys.RETURN)
        logger.info(f"Searching for '{search_term}'...")
        random_sleep()

        if gender_filters:
            apply_gender_filters(driver, gender_filters)

        page_num = 1
        while page_num <= pages_to_scrape:
            logger.info(f"Scraping page {page_num}...")
            searched_data.extend(scrape_products_on_page(driver))

            if not navigate_next_page(driver):
                break
            page_num += 1

    finally:
        driver.quit()

    save_data(searched_data, search_term)


if __name__ == "__main__":
    main()
