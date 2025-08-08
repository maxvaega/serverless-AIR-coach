from .rag import ask

def main():
    query = input("Enter the query: ").strip("'", )
    print(ask(query, "local", chat_history=False, stream=False))

if __name__ == "__main__":
    main()
