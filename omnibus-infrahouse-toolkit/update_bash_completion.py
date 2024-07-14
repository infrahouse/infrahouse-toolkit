import ast
from textwrap import dedent

script_path = "setup.py"

# Open the file and read the contents
with open(script_path, "r", encoding="UTF-8") as file:
    tree = ast.parse(file.read(), filename=script_path)


# Function to find assignments to a specific variable
def find_assignments(t, variable_name):
    for node in ast.walk(t):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == variable_name:
                    return [elt.value for elt in node.value.elts]


# Example usage
console_scripts = find_assignments(tree, "console_scripts")
with open("/tmp/infrahouse-completion", "w", encoding="UTF-8") as fp:
    for script in console_scripts:
        cmd = script.split("=")[0]
        cmd_l = cmd.replace("-", "_").lower()
        cmd_u = cmd.replace("-", "_").upper()
        print(f"``{cmd}``")
        print("-"*(len(cmd) + 4))
        print("")
        fp.write(
            f"""
_{cmd_l}_completion() {{
    local IFS=$'\\n'
    local response

    response=$(env COMP_WORDS="${{COMP_WORDS[*]}}" COMP_CWORD=$COMP_CWORD _{cmd_u}_COMPLETE=bash_complete $1)

    for completion in $response; do
        IFS=',' read type value <<< "$completion"

        if [[ $type == 'dir' ]]; then
            COMPREPLY=()
            compopt -o dirnames
        elif [[ $type == 'file' ]]; then
            COMPREPLY=()
            compopt -o default
        elif [[ $type == 'plain' ]]; then
            COMPREPLY+=($value)
        fi
    done

    return 0
 }}

_{cmd_l}_completion_setup() {{
     complete -o nosort -F _{cmd_l}_completion {cmd}
}}

_{cmd_l}_completion_setup;
    """
        )
