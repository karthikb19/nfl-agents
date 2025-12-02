import ddgs
import trafilatura
from .web_agent_utils import process_query, search_web, chunk_result

def retrieve_top_k_chunks(query):
    pass

def generate_prompt(chunks):
    pass

def generate_answer(prompt):
    pass

def main():
    # Welcome message
    print("=" * 60)
    print("🌐 Web Agent - AI-Powered Search Assistant")
    print("=" * 60)
    print("Type your query or 'quit' to exit\n")
    
    while True:
        # Modern prompt
        try:
            query = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye! 👋")
            break
        
        if not query:
            continue
            
        if query.lower() in ["q", "quit", "exit"]:
            print("\nGoodbye! 👋")
            break
        
        print()  # Blank line for spacing
        print("🔍 Processing your query...")
        
        # Refine Query to make it more optimized for searching
        refined_queries = process_query(query)
        if refined_queries:
            print(f"   → Refined: {refined_queries}")

        # Get the results for the refined query
        print("🌐 Searching the web...")
        results = search_web(refined_queries)

        # Process the results, go ahead and chunk articles and store it in a chunks table
        if results:
            print(f"   → Found {len(results)} results")
        
        for result in results:
            chunk_result(result) 
        
        # Retrieve Top K chunks based on the query
        print("📚 Retrieving relevant content...")
        top_k_chunks = retrieve_top_k_chunks(refined_queries)

        # Generate prompt with the top k chunks
        prompt = generate_prompt(top_k_chunks)

        # Generate answer
        print("🤖 Generating answer...\n")
        answer = generate_answer(prompt)

        # Print the answer with visual separator
        if answer:
            print("-" * 60)
            print(answer)
            print("-" * 60)
        else:
            print("⚠️  No answer generated")
        
        print()  # Blank line before next prompt

        

if __name__ == "__main__":
    main()