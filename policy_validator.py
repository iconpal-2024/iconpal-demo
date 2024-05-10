import sys
import argparse
from antlr4 import *
from antlr4.error.ErrorListener import ErrorListener, ConsoleErrorListener
from policy_parser import PolicyLexer, PolicyParser, CustomPolicyVisitor


class CustomErrorListener(ErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        raise Exception("Syntax error at line " + str(line) + ":" + str(column) + " " + msg)

def is_valid_snippet(policy_snippet):
    policy = InputStream(policy_snippet)
    lexer = PolicyLexer(policy)
    lexer.removeErrorListener(ConsoleErrorListener.INSTANCE)
    stream = CommonTokenStream(lexer)
  
    parser = PolicyParser(stream)
    parser.addErrorListener(CustomErrorListener())
    parser.removeErrorListener(ConsoleErrorListener.INSTANCE)
    try:
        tree = parser.statements()
    except Exception as e:
        return False

    visitor = CustomPolicyVisitor(relaxed=True)
    try:
        visitor.visit(tree)
    except Exception as e:
        return False
    return True


def is_valid_policy(policy_string):
    policy = InputStream(policy_string)
    lexer = PolicyLexer(policy)
    lexer.removeErrorListener(ConsoleErrorListener.INSTANCE)
    stream = CommonTokenStream(lexer)
  
    parser = PolicyParser(stream)
    parser.addErrorListener(CustomErrorListener())
    parser.removeErrorListener(ConsoleErrorListener.INSTANCE)
    try:
        tree = parser.policy()
    except Exception as e:
        return False, str(e)

    visitor = CustomPolicyVisitor()
    try:
        visitor.visit(tree)
    except Exception as e:
        return False, str(e)
    return True, ""
