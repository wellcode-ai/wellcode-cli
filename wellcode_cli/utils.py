from colorama import Fore, Back, Style

def color_print(text, color=Fore.WHITE, bg_color=Back.BLACK, style=Style.NORMAL, end='\n'):
    print(f"{style}{bg_color}{color}{text}{Style.RESET_ALL}", end=end)

# Usage examples:
# color_print("Success!", Fore.GREEN)
# color_print("Warning", Fore.YELLOW)
# color_print("Error", Fore.RED)
# color_print("Important", Fore.WHITE, Back.BLUE)