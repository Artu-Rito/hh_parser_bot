import requests
import fake_useragent
from bs4 import BeautifulSoup
import time
import re

def get_resume_links(text):
    ua = fake_useragent.UserAgent()
    data = requests.get(
        url=f"https://hh.ru/search/resume?area=1&isDefaultArea=true&exp_period=all_time&logic=normal&pos=full_text&fromSearchLine=true&from=employer_index_header&text={text}&page=1",
        headers={"user-agent":ua.random}
    )
    if data.status_code != 200:
        return
    soup = BeautifulSoup(data.content, "lxml")
    try:
        page_count = int(soup.find("div", attrs={"class":"pager"}).find_all("span", recursive=False)[-1].find("a").find("span").text)
    except:
        return
    for page in range(page_count):
        try:
            data = requests.get(
                url=f"https://hh.ru/search/resume?area=1&isDefaultArea=true&exp_period=all_time&logic=normal&pos=full_text&fromSearchLine=true&from=employer_index_header&text={text}&page={page}",
                headers={"user-agent": ua.random}
            )
            if data.status_code != 200:
                continue
            soup = BeautifulSoup(data.content, "lxml")
            for a in soup.find_all("a", attrs={"class":"bloko-link"}):
                href = a.attrs['href']
                if "/resume/" in href and "advanced" not in href.split("/resume/")[1]:
                    yield f"https://hh.ru{a.attrs['href'].split('?')[0]}"
        except Exception as e:
            print(f"{e}")
        time.sleep(1)

def get_resume(link):
    ua = fake_useragent.UserAgent()
    data = requests.get(
        url=link,
        headers={"user-agent":ua.random}
    )
    if data.status_code != 200:
        return "Ошибка доступа к странице: статус " + str(data.status_code)
    soup = BeautifulSoup(data.content,"lxml")
    try:
        name = soup.find(attrs={"class":"resume-block__title-text"}).text
    except:
        name = "not specified"
    try:
        salary = soup.find(attrs={"class":"resume-block__salary"}).text.replace("\u2009","").replace("\xa0","").split("₽")[0]
    except:
        salary = "not specified"
    try:
        tags = [tag.text for tag in soup.find(attrs={"class": "bloko-tag-list"}).find_all(attrs={"class":"bloko-tag__section_text"})]
    except:
        tags = []
    try:
        work_exp = soup.find(attrs={"class": "resume-block__title-text resume-block__title-text_sub"}).text.replace(
            "\xa0", "")
        # Удаляем все до первой цифры
        work_exp = re.sub(r'^.*?(\d)', r'\1', work_exp)
        # Заменяем обозначения лет и месяцев на 'y' и 'm'
        work_exp = re.sub(r'(\d+)\s*(года|год|years?|лет)', r'\1y', work_exp)
        work_exp = re.sub(r'(\d+)\s*(месяца|месяцев|months?)', r'\1m', work_exp)
    except:
        work_exp = "not specified"
    resume = {
        "name": name,
        "salary": salary,
        "work_exp": work_exp,
        "tags": tags,
        "link": link
    }
    return resume

def get_vacanсy_links(text):
    ua = fake_useragent.UserAgent()
    data = requests.get(
        url=f"https://hh.ru/search/vacancy?text={text}&salary=&ored_clusters=true&area=1&page=1",
        headers={"user-agent":ua.random}
    )
    if data.status_code != 200:
        return
    soup = BeautifulSoup(data.content, "lxml")
    try:
        page_count = int(soup.find("div", attrs={"class":"pager"}).find_all("span", recursive=False)[-1].find("a").find("span").text)
    except:
        return
    for page in range(page_count):
        try:
            data = requests.get(
                url=f"https://hh.ru/search/vacancy?text={text}&salary=&ored_clusters=true&area=1&page={page}",
                headers={"user-agent": ua.random}
            )
            if data.status_code != 200:
                continue
            soup = BeautifulSoup(data.content, "lxml")
            for a in soup.find_all("a", attrs={"class":"bloko-link"}):
                href = a.attrs['href']
                if "vacancy/" in href:
                    yield f"{a.attrs['href'].split('?')[0]}"
        except Exception as e:
            print(f"{e}")
        time.sleep(1)

def get_vacancy(link):
    ua = fake_useragent.UserAgent()
    data = requests.get(
        url=link,
        headers={"user-agent":ua.random}
    )
    if data.status_code != 200:
        return
    soup = BeautifulSoup(data.content,"lxml")
    try:
        job_name = soup.find(attrs={"class":"bloko-header-section-1"}).text
    except:
        job_name = "not specified"
    try:
        company_name = soup.find(attrs={"class":"vacancy-company-name"}).text.replace("\xa0"," ")
    except:
        company_name = "not specified"
    try:
        salary = soup.find(attrs={"class":"magritte-text___pbpft_3-0-8 magritte-text_style-primary___AQ7MW_3-0-8 magritte-text_typography-label-1-regular___pi3R-_3-0-8"}).text.replace("\xa0","")
    except:
        salary = "not specified"
    try:
        skills = [tag.text for tag in soup.find(attrs={"class": "vacancy-skill-list--COfJZoDl6Y8AwbMFAh5Z"}).find_all(attrs={"class":"magritte-tag__label___YHV-o_3-0-0"})]
    except:
        skills = ["not specified"]
    vacancy = {
        "job_name": job_name,
        "company_name": company_name,
        "salary": salary,
        "skills": skills,
        "link": link
    }
    return vacancy

if __name__ == "__main__":
    for a in get_resume_links("python"):
        print(get_resume(a))
        time.sleep(1)