from .rag import ask
import asyncio

def main():
    query = input("Enter the query: ").strip("'", )
    print(ask(query, "local-user", stream=False))

if __name__ == "__main__":
    main()
