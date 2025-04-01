from code_agent import CodeAssistant
from dotenv import load_dotenv
import traceback
load_dotenv()

def main():
    print("🤖 GitHub Code Assistant")
    print("Type 'quit' to exit\n")
    
    assistant = CodeAssistant()
    
    while True:
        try:
            query = input("\nYou: ")
            if query.lower() in ('quit', 'exit'):
                break

            # Determine action
            assistant.process_query(query)
            
        except Exception as e:
            print(traceback.format_exc())
            continue

if __name__ == "__main__":
    main()