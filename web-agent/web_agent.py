from ddgs import DDGS
import trafilatura

results = DDGS().text("python programming", max_results=5)
for result in results:
    print(result)



html = trafilatura.fetch_url(results[0]['href'])

text = trafilatura.extract(html)

print(len(text))  # print first 800 characters
