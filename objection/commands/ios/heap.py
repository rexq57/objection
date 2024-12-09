import pprint
from typing import Any

import click
from prompt_toolkit import prompt
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.javascript import JavascriptLexer
from tabulate import tabulate

from objection.state.connection import state_connection


def _should_ignore_methods_with_arguments(args) -> bool:
    """
        Check if the --without-arguments flag exists

        :param args:
        :return:
    """

    return len(args) > 0 and '--without-arguments' in args


def _should_print_as_utf8(args) -> bool:
    """
        Check if the --to-utf8 flag exists

        :param args:
        :return:
    """

    return len(args) > 0 and '--to-utf8' in args


def _should_return_as_string(args) -> bool:
    """
        Check if the --return-string flag exists

        :param args:
        :return:
    """

    return len(args) > 0 and '--return-string' in args


def _should_interpret_inline_js(args) -> bool:
    """
        Check if we have the --inline flag

        :param args:
        :return:
    """

    return len(args) > 0 and '--inline' in args


def instances(args: list) -> None:
    """
        Asks the agent to print the currently live instances of a particular class

        :param args:
        :return:
    """

    if len(args) < 1:
        click.secho('Usage: ios heap search instances <class> (eg: com.example.test)', bold=True)
        return

    target_class = args[0]

    api = state_connection.get_api()
    instance_results = api.ios_heap_print_live_instances(target_class)

    # export interface IHeapObject {
    #   className: string;
    #   handle: string;
    #   ivars: any[string];
    #   kind: string;
    #   methods: string[];
    #   superClass: string;
    # }

    if len(instance_results) <= 0:
        return

    click.secho(tabulate(
        [[
            entry['handle'],
            entry['kind'],
            entry['className'],
            entry['superClass'],
            len(entry['ivars']),
            len(entry['methods'])
        ] for entry in instance_results], headers=['Handle', 'Kind', 'Class', 'Super', 'iVars', 'Methods'],
    ))


def ivars(args: list) -> None:
    """
        Get ivars for an Objective-C object at a pointer

        :param args:
        :return:
    """

    if len(args) < 1:
        click.secho('Usage: ios heap print ivars <pointer> (eg: 0x600001130660)', bold=True)
        return

    target_pointer = args[0]

    api = state_connection.get_api()
    ivar_results = api.ios_heap_print_ivars(target_pointer, _should_print_as_utf8(args))

    def format_class_and_value(value: Any) -> tuple:
        """Format value with quotes for strings and prepare className:pointer."""
        if isinstance(value, dict) and 'className' in value and 'pointer' in value:
            class_and_pointer = f"<{value['className']}:{value['pointer']}>"
            raw_value = value.get('value', '')
        else:
            class_and_pointer = ''
            raw_value = value

        # If the value is a string, wrap it in quotes and escape special characters
        if isinstance(raw_value, str):
            formatted_value = repr(raw_value)
        else:
            formatted_value = raw_value

        return formatted_value, class_and_pointer

    # Prepare table data with iVar, Value, and className:Pointer
    table_data = [
        [key, formatted_value, class_and_pointer]
        for key, raw_value in ivar_results[1].items()
        for formatted_value, class_and_pointer in [format_class_and_value(raw_value)]
    ]

    # Display the table with swapped columns
    click.secho(tabulate(
        table_data,
        headers=['iVar', 'Value', '<className:pointer>'],
    ))



def methods(args: list) -> None:
    """
        Get methods for an Objective-C object at a pointer

        :param args:
        :return:
    """

    if len(args) < 1:
        click.secho('Usage: ios heap print methods <pointer> (eg: 0x600001130660)', bold=True)
        return

    target_pointer = args[0]

    api = state_connection.get_api()
    method_results = api.ios_heap_print_methods(target_pointer)

    # apply argument filters
    if _should_ignore_methods_with_arguments(args):
        method_results[1] = list(filter(lambda x: ':' not in x, method_results[1]))

    click.secho(tabulate(
        [[
            entry,
            entry.split(" ")[0],
            "{type} [{clazz} {method}]".format(  # hacky, right? :D
                type=entry.split(" ")[0], clazz=method_results[0], method=entry.split(" ")[1])
        ] for entry in method_results[1]], headers=['Method', 'Type', 'Full'],
    ))


def execute(args: list) -> None:
    """
        Executes a method on a pointer which is assumed to be an Objective-C
        object.

        :param args:
        :return:
    """

    if len(args) < 1:
        click.secho('Usage: ios heap execute method <pointer> <method> (eg: 0x600001130660)', bold=True)
        return

    target_pointer = args[0]
    method = args[1]

    if ':' in method:
        click.secho('Unfortunately, only methods that do not require arguments are supported.', fg='yellow')
        return

    api = state_connection.get_api()
    exec_results = api.ios_heap_exec_method(target_pointer, method, _should_return_as_string(args))

    click.secho(pprint.pformat(exec_results))


def evaluate(args: list) -> None:
    """
        Evaluate JavaScript on an Objective-C pointer.

        :param args:
        :return:
    """

    if len(args) < 1:
        click.secho('Usage: ios heap execute js <pointer> (eg: 0x600001130660) ' +
                    '(optional: --inline) (optional: <JavaScript source>)', bold=True)
        return

    target_pointer = args[0]

    # adding the --inline flag would trigger reading the line contents
    # as JavaScript sources
    if _should_interpret_inline_js(args):
        args.remove('--inline')
        js = ''.join(args[1:])

        click.secho('Reading inline JavaScript for evaluation...', dim=True)
        click.secho('{}\n'.format(js), fg='green', dim=True)

    else:
        js = prompt(
            click.secho('(The pointer at `{pointer}` will be available as the `ptr` variable.)n'.format(
                pointer=target_pointer
            ), dim=True),
            multiline=True, lexer=PygmentsLexer(JavascriptLexer),
            bottom_toolbar='JavaScript edit mode. [ESC] and then [ENTER] to accept. [CTRL] + C to cancel.').strip()

        click.secho('JavaScript capture complete. Evaluating...', dim=True)

    api = state_connection.get_api()
    api.ios_heap_evaluate_js(target_pointer, js)
