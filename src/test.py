from .rag import ask
import asyncio

def main():
    query = input("Enter the query: ").strip("'", )
    asyncio.run(ask(query, stream=False))

if __name__ == "__main__":
    main()
