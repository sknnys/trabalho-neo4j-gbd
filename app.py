from flask import Flask, render_template, request, redirect, url_for
from neo4j import GraphDatabase
from bs4 import BeautifulSoup
import requests
import re 

app = Flask(__name__)

uri = "neo4j+s://5d2e5152.databases.neo4j.io:7687"  
username = "neo4j"  
password = "VkxKaiVosysOVAJALSxysXmeFDl63Lr7_i5WwDTkRow"  
driver = GraphDatabase.driver(uri, auth=(username, password))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    keyword_input = request.form['keyword']
    keywords = extract_keywords(keyword_input) 
    articles = fetch_articles_by_keyword(keyword_input)
    insert_articles(articles, keywords)  
    return redirect(url_for('index'))

def extract_keywords(keyword_input):
    return re.findall(r'\*(.*?)\*', keyword_input)

def fetch_articles_by_keyword(keyword):
    url = f"https://scholar.google.com/scholar?q={keyword}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = []

        for result in soup.find_all('div', class_='gs_ri'):
            title = result.find('h3', class_='gs_rt').text
            title_cleaned = re.sub(r'\[.*?\]', '', title).strip()

            author_info = result.find('div', class_='gs_a').text
            authors = author_info.split(' - ')[0].split(', ')
            authors_cleaned = [author for author in authors if not re.search(r'\d{4}', author)]

            year_match = re.search(r'\d{4}', author_info)
            publication_year = year_match.group(0) if year_match else 'Data não disponível'

            articles.append({
                'title': title_cleaned,
                'authors': authors_cleaned,
                'publication_year': publication_year
            })
        return articles
    return []

def insert_article(tx, title, authors, publication_year, keywords):
    for keyword in keywords:
        tx.run("MERGE (k:Keyword {name: $keyword})", keyword=keyword)
        
        tx.run("CREATE (a:Article {title: $title, publication_year: $publication_year})", 
               title=title, publication_year=publication_year)
        
        tx.run("MATCH (k:Keyword {name: $keyword}), (a:Article {title: $title}) "
               "CREATE (k)-[:RELATED_TO]->(a)", keyword=keyword, title=title)
    
    for author in authors:
        tx.run("MERGE (au:Author {name: $name})", name=author)
        tx.run("MATCH (a:Article {title: $title}), (au:Author {name: $name}) "
               "CREATE (au)-[:WROTE]->(a)", title=title, name=author)

def insert_articles(articles, keywords):
    with driver.session() as session:
        for article in articles:
            session.write_transaction(
                insert_article, 
                article['title'], 
                article['authors'], 
                article['publication_year'], 
                keywords  
            )

if __name__ == '__main__':
    app.run(debug=True, port=5001)