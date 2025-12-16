import requests
from bs4 import BeautifulSoup
import time
import pandas as pd
import re
import os
import html

BASE_URL = "https://companies.rbc.ru"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': BASE_URL,
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def get_page(url):
    try:
        print(f"Запрос страницы: {url}")
        
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        if 'text/html' not in response.headers.get('Content-Type', '').lower():
            print(f"Предупреждение: Получен не HTML контент для {url}")
            return None
        
        time.sleep(2)
        
        return response.text
    
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе страницы {url}: {e}")
        return None

def parse_revenue_value(revenue_text):
    try:
        decoded_text = html.unescape(revenue_text)
        
        cleaned_text = decoded_text.replace('₽', '').replace('\xa0', ' ').replace('&nbsp;', ' ').strip()
        
        numbers_only = re.sub(r'[^\d\.,]', '', cleaned_text)
        
        numbers_only = numbers_only.replace(',', '.')
        
        parts = numbers_only.split('.')
        if len(parts) > 1:
            integer_part = ''.join(parts[:-1])
            decimal_part = parts[-1][:2]
            value_str = f"{integer_part}.{decimal_part}"
        else:
            value_str = parts[0]
        
        return float(value_str) if value_str else 0.0
    
    except Exception as e:
        print(f"Ошибка при преобразовании выручки '{revenue_text}': {e}")
        return 0.0

def parse_company_element(element):
    data = {}
    
    try:
        name_paragraph = element.find('p', string=lambda text: text and '»' in text or '«' in text)
        if name_paragraph and name_paragraph.text.strip():
            data['name'] = name_paragraph.text.strip()
        else:
            name_link = element.find('a', class_='company-name-highlight')
            if name_link:
                name_span = name_link.find('span')
                if name_span:
                    data['name'] = name_span.get('title', '').strip() or name_span.text.strip()
        
        inn_element = element.find('span', string=re.compile(r'ИНН:'))
        if inn_element:
            parent = inn_element.parent
            inn_text = parent.get_text(strip=True).replace('ИНН:', '').strip()
            data['inn'] = inn_text
        
        revenue_element = element.find('span', string=re.compile(r'Выручка:'))
        if revenue_element:
            parent = revenue_element.parent
            revenue_text = parent.get_text(strip=True).replace('Выручка:', '').strip()
            data['revenue_text'] = revenue_text
            data['revenue_value'] = parse_revenue_value(revenue_text)
    
    except Exception as e:
        print(f"Ошибка при парсинге элемента компании: {e}")
    
    return data

def parse_page(html_content):
    if not html_content:
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    company_elements = soup.find_all('div', class_='company-card')
    
    companies = []
    qualifying_companies = []
    
    for element in company_elements:
        company_data = parse_company_element(element)
        if company_data:
            companies.append(company_data)
            revenue_value = company_data.get('revenue_value', 0)
            if revenue_value > 100000000:  # 100 млн рублей
                qualifying_companies.append(company_data)
                print(f" Найдена компания с выручкой > 100 млн: {company_data.get('name', 'Без названия')} | Выручка: {company_data.get('revenue_text', 'Не указана')}")
            else:
                print(f" Пропущена компания: {company_data.get('name', 'Без названия')} | Выручка: {company_data.get('revenue_text', 'Не указана')} (менее 100 млн)")
    
    print(f" Всего компаний на странице: {len(companies)}")
    print(f" Компаний с выручкой > 100 млн на странице: {len(qualifying_companies)}")
    return qualifying_companies

def parse_all_pages(base_url, max_pages=20):
    all_companies = []
    page_num = 1
    
    print(f"\n{'='*60}")
    print(f"НАЧАЛО ПАРСИНГА КОМПАНИЙ ПЕРЕВОДОВ")
    print(f"Базовый URL: {base_url}")
    print(f"Фильтр: выручка > 100 млн рублей")
    print(f"Максимальное количество страниц: {max_pages}")
    print(f"{'='*60}")
    
    while page_num <= max_pages:
        if page_num == 1:
            url = base_url
        else:
            clean_base_url = base_url.rstrip('/')
            url = f"{clean_base_url}/{page_num}/"
        
        print(f"\n{'='*60}")
        print(f"СТРАНИЦА {page_num}")
        print(f"URL: {url}")
        print(f"{'='*60}")
        
        html_content = get_page(url)
        
        if not html_content:
            print(f" Не удалось загрузить страницу {page_num}.")
            page_num += 1
            continue
        
        companies = parse_page(html_content)
        
        all_companies.extend(companies)
        
        print(f" Добавлено {len(companies)} компаний со страницы {page_num}")
        print(f" Всего компаний с выручкой > 100 млн: {len(all_companies)}")
        
        page_num += 1
    
    print(f"\n{'='*60}")
    print(f"ПАРСИНГ ЗАВЕРШЕН")
    print(f"Всего компаний с выручкой > 100 млн: {len(all_companies)}")
    print(f"Обработано страниц: {page_num-1}")
    print(f"{'='*60}")
    
    return all_companies

def save_to_excel(data, filename=None):
    if not data:
        print("Нет данных для сохранения в Excel")
        return False
    
    try:
        os.makedirs('results', exist_ok=True)
        
        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"translation_companies_revenue_over_100m_{timestamp}.xlsx"
        
        full_path = os.path.join('results', filename)
        
        excel_data = []
        for company in data:
            excel_data.append({
                'Название компании': company.get('name', 'Не указано'),
                'ИНН': company.get('inn', 'Не указан'),
                'Выручка': company.get('revenue_text', 'Не указана'),
            })
        
        df = pd.DataFrame(excel_data)
        
        df.to_excel(full_path, index=False)
        
        print(f"Данные успешно сохранены в Excel: {full_path}")
        return full_path
    
    except Exception as e:
        print(f"Ошибка при сохранении в Excel: {e}")
        return False

def main():
    print("ЗАПУСК ПАРСЕРА")
    print("=" * 60)
    
    category_url = "https://companies.rbc.ru/category/788-ustnye_i_pismennye_perevody/"
    
    MAX_PAGES = 10
    
    all_companies = parse_all_pages(category_url, MAX_PAGES)
    
    if all_companies:
        excel_path = save_to_excel(all_companies)
        
        print(f"\n Парсинг завершен успешно!")
        print(f" Найдено компаний с выручкой > 100 млн: {len(all_companies)}")
        if excel_path:
            print(f" Результаты сохранены в файле: {excel_path}")
    else:
        print(f"\n Не удалось найти компании с выручкой > 100 млн рублей")
        print(" Обработаны все доступные страницы, но компании, прошедших фильтр не найдено.")
    
    return True

if __name__ == "__main__":
    main()
    
    print("\n СКРИПТ ЗАВЕРШЕН")