from rich.console import Console
from rich.markdown import Markdown
from ..utils import  get_latest_analysis
import rich_click as click

import anthropic
from .config import load_config
from rich.prompt import Prompt
console = Console()
from .review import review


@click.command()
@click.argument('initial_question', required=False)
def chat(initial_question=None):
    """Interactive chat about your engineering metrics"""
    # Get the latest analysis data
    data = get_latest_analysis()
    if not data:
        console.print("[yellow]No recent analysis found. Running new analysis...[/]\n")
        ctx = click.get_current_context()
        ctx.invoke(review)
        data = get_latest_analysis()
    
    # Load configuration
    config_data = load_config()
    if not config_data.get('ANTHROPIC_API_KEY'):
        console.print("[red]Error: Anthropic API key not configured. Please run 'wellcode-cli config'[/]")
        return

    client = anthropic.Client(api_key=config_data['ANTHROPIC_API_KEY'])
    
    console.print("[bold blue]Wellcode AI Chat[/]")
    console.print("Ask questions about your engineering metrics. Type 'exit' to quit.\n")

    # Initialize system prompt
    system_prompt = f"""You are an engineering metrics analyst. You have access to the following data:

<metrics>
{data['metrics']}
</metrics>

You also have access to a previous analysis:

<previous_analysis>
{data['analysis']}
</previous_analysis>

Your task is to answer questions about this data in a clear, concise way. Follow these guidelines:

1. Use specific numbers and metrics when relevant to support your answers.
2. When asked about trends or patterns, refer to the actual data points provided in the metrics.
3. If asked for recommendations, base them on the specific metrics and context provided in both the metrics and previous analysis.
4. Ensure your answers are directly related to the engineering metrics and context provided.
5. If the question cannot be answered based on the given information, state this clearly and explain why.

Before providing your final answer, use a <scratchpad> to organize your thoughts and identify relevant data points. This will help you structure a comprehensive response.

Format your response as follows:
1. <scratchpad> (for your thought process)
2. <answer> (for your final, polished response)


Please provide your analysis and answer based on the given metrics and previous analysis."""

    # Initialize conversation history
    messages = []

    # If there's an initial question, process it without welcome messages
    if initial_question:
        messages = []
        messages.append({"role": "user", "content": initial_question})
        with console.status("[bold green]Thinking..."):
            response = client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2048,
                messages=messages,
                system=system_prompt
            )
            assistant_message = response.content[0].text
            console.print("\n[bold green]Answer:[/]")
            console.print(Markdown(assistant_message))      
            return False  # Signal to return to main prompt

    # Continue with interactive chat
    while True:
        # Get user input
        question = Prompt.ask("\n[cyan]What would you like to know about your metrics?[/]")
        
        if question.lower() in ['exit', 'quit', 'q']:
            break

        with console.status("[bold green]Thinking..."):
            # Add user question to messages
            messages.append({"role": "user", "content": question})
            
            # Get response from Claude
            response = client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2048,
                messages=messages,
                system=system_prompt
            )
            
            # Add assistant response to messages
            assistant_message = response.content[0].text
            messages.append({"role": "assistant", "content": assistant_message})

        # Display response with markdown formatting
        console.print("\n[bold green]Answer:[/]")
        console.print(Markdown(assistant_message))
