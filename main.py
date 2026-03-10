#!/usr/bin/env python3
"""
TNEA College Counselling Assistant

Main entry point for the college counselling assistant with database integrations.

Usage:
    python main.py              # Interactive mode
    python main.py introspect   # Show database schema
    python main.py schema       # Show schema as JSON
"""

import asyncio
import sys
import os

from dotenv import load_dotenv


async def main_interactive():
    """Run the agent in interactive mode"""
    load_dotenv()
    
    from src.src.agents import college_agent
    from src.src.tools import database_introspection_tool
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ Error: DATABASE_URL not configured")
        print("Please set DATABASE_URL in .env file")
        return
    
    print("🎓 TNEA College Counselling Assistant")
    print("=" * 50)
    print("Type 'exit' to quit\n")
    
    # Try to load schema once
    try:
        print("📚 Loading database schema...")
        schema = await database_introspection_tool(db_url)
        print(f"✅ Connected to {schema.database}")
        print(f"📊 Tables: {', '.join([t.table_name for t in schema.tables])}\n")
    except Exception as e:
        print(f"❌ Database error: {e}\n")
        return
    
    # Interactive loop
    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ["exit", "quit", "q"]:
                print("👋 Goodbye!")
                break
            
            if not user_input:
                continue
            
            # Process query
            print("🔄 Processing...\n")
            result = await college_agent.process_query(user_input, db_url)
            
            if result["success"]:
                print(f"Agent: {result.get('response', 'Processing complete.')}\n")
            else:
                print(f"❌ Error: {result.get('error', 'Unknown error')}\n")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")


def show_schema():
    """Display database schema as JSON"""
    import json
    from introspect import main as introspect_main
    
    print("Running introspection...")
    asyncio.run(introspect_main())


async def show_schema_json():
    """Display database schema as JSON"""
    import json
    from src.src.tools import database_introspection_tool
    
    load_dotenv()
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ Error: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)
    
    from show_schema import main as show_schema_main
    await show_schema_main()


def show_help():
    """Display help information"""
    print("""
TNEA College Counselling Assistant

Usage:
    python main.py [command]

Commands:
    (no arguments)      Interactive mode
    introspect          Show database schema and table info
    schema              Display database schema as JSON
    help                Show this help message

Environment:
    DATABASE_URL        MySQL connection string
    MODEL               LLM model (default: groq/llama-3.3-70b-versatile)

Examples:
    DATABASE_URL=mysql://user:pass@host/db python main.py
    python main.py introspect
    python main.py schema
    """)


async def main():
    """Main entry point"""
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command in ["help", "-h", "--help", "?"]:
            show_help()
        elif command == "introspect":
            from introspect import main as introspect_main
            await introspect_main()
        elif command == "schema":
            from show_schema import main as show_schema_main
            await show_schema_main()
        else:
            print(f"Unknown command: {command}")
            print("Use 'python main.py help' for usage information")
            sys.exit(1)
    else:
        # Run interactive mode
        await main_interactive()


if __name__ == "__main__":
    asyncio.run(main())
