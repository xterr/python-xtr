# ruff: noqa: E501 -- the expected dumps are byte-exact; their lines cannot wrap.
"""A Graphviz dump draws places as circles and transitions as boxes, byte for byte."""

from __future__ import annotations

import pytest

from tests.support.definitions import (
    create_complex_workflow_definition,
    create_simple_workflow_definition,
    create_workflow_with_metadata_edge_cases,
)
from xtr_workflow import Arc, Definition, Marking, Transition
from xtr_workflow.dumper import GraphvizDumper
from xtr_workflow.metadata import InMemoryMetadataStore

COMPLEX_WORKFLOW_DUMP_WITH_MARKING = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle color="#FF0000" shape="doublecircle"];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label=<<B>c</B>>, shape=circle];
  place_3c363836cf4e16666669a25da280a1865c2d2874 [label=<<B>d</B>>, shape=circle];
  place_58e6b3a414a1e090dfc6029add0f3555ccba127f [label=<<B>e</B>>, shape=circle];
  place_4a0a19218e082a343a1b17e5333409af9d98f0f5 [label=<<B>f</B>>, shape=circle];
  place_54fd1711209fb1c0781092374132c66e79e2241b [label=<<B>g</B>>, shape=circle];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [label=<<B>t1</B>>, shape="box" regular="1"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab [label=<<B>t2</B>>, shape="box" regular="1"];
  transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 [label=<<B>My custom transition label 1</B>>, shape="box" regular="1"];
  transition_77de68daecd823babbb58edb1c8e14d7106e83bb [label=<<B>t4</B>>, shape="box" regular="1"];
  transition_1b6453892473a467d07372d45eb05abc2031647a [label=<<B>t5</B>>, shape="box" regular="1"];
  transition_ac3478d69a3c81fa62e60f5c3696165a4e5e6ac4 [label=<<B>t6</B>>, shape="box" regular="1"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [style="solid"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> transition_356a192b7913b04c54574d18c28d46e6395428ab [style="solid"];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 -> transition_356a192b7913b04c54574d18c28d46e6395428ab [style="solid"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab -> place_3c363836cf4e16666669a25da280a1865c2d2874 [style="solid"];
  place_3c363836cf4e16666669a25da280a1865c2d2874 -> transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 [style="solid"];
  transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 -> place_58e6b3a414a1e090dfc6029add0f3555ccba127f [style="solid"];
  place_3c363836cf4e16666669a25da280a1865c2d2874 -> transition_77de68daecd823babbb58edb1c8e14d7106e83bb [style="solid"];
  transition_77de68daecd823babbb58edb1c8e14d7106e83bb -> place_4a0a19218e082a343a1b17e5333409af9d98f0f5 [style="solid"];
  place_58e6b3a414a1e090dfc6029add0f3555ccba127f -> transition_1b6453892473a467d07372d45eb05abc2031647a [style="solid"];
  transition_1b6453892473a467d07372d45eb05abc2031647a -> place_54fd1711209fb1c0781092374132c66e79e2241b [style="solid"];
  place_4a0a19218e082a343a1b17e5333409af9d98f0f5 -> transition_ac3478d69a3c81fa62e60f5c3696165a4e5e6ac4 [style="solid"];
  transition_ac3478d69a3c81fa62e60f5c3696165a4e5e6ac4 -> place_54fd1711209fb1c0781092374132c66e79e2241b [style="solid"];
}
"""

COMPLEX_WORKFLOW_DUMP_WITH_MARKING_AND_METADATA = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle color="#FF0000" shape="doublecircle"];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label=<<B>c</B>>, shape=circle];
  place_3c363836cf4e16666669a25da280a1865c2d2874 [label=<<B>d</B>>, shape=circle];
  place_58e6b3a414a1e090dfc6029add0f3555ccba127f [label=<<B>e</B>>, shape=circle];
  place_4a0a19218e082a343a1b17e5333409af9d98f0f5 [label=<<B>f</B>>, shape=circle];
  place_54fd1711209fb1c0781092374132c66e79e2241b [label=<<B>g</B>>, shape=circle];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [label=<<B>t1</B>>, shape="box" regular="1"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab [label=<<B>t2</B>>, shape="box" regular="1"];
  transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 [label=<<B>My custom transition label 1</B><BR/>color: Red<BR/>arrow_color: Green>, shape="box" regular="1"];
  transition_77de68daecd823babbb58edb1c8e14d7106e83bb [label=<<B>t4</B>>, shape="box" regular="1"];
  transition_1b6453892473a467d07372d45eb05abc2031647a [label=<<B>t5</B>>, shape="box" regular="1"];
  transition_ac3478d69a3c81fa62e60f5c3696165a4e5e6ac4 [label=<<B>t6</B>>, shape="box" regular="1"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [style="solid"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> transition_356a192b7913b04c54574d18c28d46e6395428ab [style="solid"];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 -> transition_356a192b7913b04c54574d18c28d46e6395428ab [style="solid"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab -> place_3c363836cf4e16666669a25da280a1865c2d2874 [style="solid"];
  place_3c363836cf4e16666669a25da280a1865c2d2874 -> transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 [style="solid"];
  transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 -> place_58e6b3a414a1e090dfc6029add0f3555ccba127f [style="solid"];
  place_3c363836cf4e16666669a25da280a1865c2d2874 -> transition_77de68daecd823babbb58edb1c8e14d7106e83bb [style="solid"];
  transition_77de68daecd823babbb58edb1c8e14d7106e83bb -> place_4a0a19218e082a343a1b17e5333409af9d98f0f5 [style="solid"];
  place_58e6b3a414a1e090dfc6029add0f3555ccba127f -> transition_1b6453892473a467d07372d45eb05abc2031647a [style="solid"];
  transition_1b6453892473a467d07372d45eb05abc2031647a -> place_54fd1711209fb1c0781092374132c66e79e2241b [style="solid"];
  place_4a0a19218e082a343a1b17e5333409af9d98f0f5 -> transition_ac3478d69a3c81fa62e60f5c3696165a4e5e6ac4 [style="solid"];
  transition_ac3478d69a3c81fa62e60f5c3696165a4e5e6ac4 -> place_54fd1711209fb1c0781092374132c66e79e2241b [style="solid"];
}
"""

SIMPLE_WORKFLOW_DUMP_WITH_MARKING = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label=<<B>c</B>>, shape=circle color="#FF0000" shape="doublecircle" style="filled" fillcolor="DeepSkyBlue"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [label=<<B>My custom transition label 2</B>>, shape="box" regular="1"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab [label=<<B>t2</B>>, shape="box" regular="1"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [style="solid"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> transition_356a192b7913b04c54574d18c28d46e6395428ab [style="solid"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab -> place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [style="solid"];
}
"""

SIMPLE_WORKFLOW_DUMP_WITH_MARKING_AND_METADATA = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label=<<B>c</B><BR/><I>My custom place description</I>>, shape=circle color="#FF0000" shape="doublecircle" style="filled" fillcolor="DeepSkyBlue"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [label=<<B>My custom transition label 2</B><BR/>color: Grey<BR/>arrow_color: Purple>, shape="box" regular="1"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab [label=<<B>t2</B><BR/>arrow_color: Pink>, shape="box" regular="1"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [style="solid"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> transition_356a192b7913b04c54574d18c28d46e6395428ab [style="solid"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab -> place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [style="solid"];
}
"""

COMPLEX_WORKFLOW_DUMP_WITHOUT_MARKING = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label=<<B>c</B>>, shape=circle];
  place_3c363836cf4e16666669a25da280a1865c2d2874 [label=<<B>d</B>>, shape=circle];
  place_58e6b3a414a1e090dfc6029add0f3555ccba127f [label=<<B>e</B>>, shape=circle];
  place_4a0a19218e082a343a1b17e5333409af9d98f0f5 [label=<<B>f</B>>, shape=circle];
  place_54fd1711209fb1c0781092374132c66e79e2241b [label=<<B>g</B>>, shape=circle];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [label=<<B>t1</B>>, shape="box" regular="1"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab [label=<<B>t2</B>>, shape="box" regular="1"];
  transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 [label=<<B>My custom transition label 1</B>>, shape="box" regular="1"];
  transition_77de68daecd823babbb58edb1c8e14d7106e83bb [label=<<B>t4</B>>, shape="box" regular="1"];
  transition_1b6453892473a467d07372d45eb05abc2031647a [label=<<B>t5</B>>, shape="box" regular="1"];
  transition_ac3478d69a3c81fa62e60f5c3696165a4e5e6ac4 [label=<<B>t6</B>>, shape="box" regular="1"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [style="solid"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> transition_356a192b7913b04c54574d18c28d46e6395428ab [style="solid"];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 -> transition_356a192b7913b04c54574d18c28d46e6395428ab [style="solid"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab -> place_3c363836cf4e16666669a25da280a1865c2d2874 [style="solid"];
  place_3c363836cf4e16666669a25da280a1865c2d2874 -> transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 [style="solid"];
  transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 -> place_58e6b3a414a1e090dfc6029add0f3555ccba127f [style="solid"];
  place_3c363836cf4e16666669a25da280a1865c2d2874 -> transition_77de68daecd823babbb58edb1c8e14d7106e83bb [style="solid"];
  transition_77de68daecd823babbb58edb1c8e14d7106e83bb -> place_4a0a19218e082a343a1b17e5333409af9d98f0f5 [style="solid"];
  place_58e6b3a414a1e090dfc6029add0f3555ccba127f -> transition_1b6453892473a467d07372d45eb05abc2031647a [style="solid"];
  transition_1b6453892473a467d07372d45eb05abc2031647a -> place_54fd1711209fb1c0781092374132c66e79e2241b [style="solid"];
  place_4a0a19218e082a343a1b17e5333409af9d98f0f5 -> transition_ac3478d69a3c81fa62e60f5c3696165a4e5e6ac4 [style="solid"];
  transition_ac3478d69a3c81fa62e60f5c3696165a4e5e6ac4 -> place_54fd1711209fb1c0781092374132c66e79e2241b [style="solid"];
}
"""

COMPLEX_WORKFLOW_DUMP_WITHOUT_MARKING_WITH_METADATA = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label=<<B>c</B>>, shape=circle];
  place_3c363836cf4e16666669a25da280a1865c2d2874 [label=<<B>d</B>>, shape=circle];
  place_58e6b3a414a1e090dfc6029add0f3555ccba127f [label=<<B>e</B>>, shape=circle];
  place_4a0a19218e082a343a1b17e5333409af9d98f0f5 [label=<<B>f</B>>, shape=circle];
  place_54fd1711209fb1c0781092374132c66e79e2241b [label=<<B>g</B>>, shape=circle];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [label=<<B>t1</B>>, shape="box" regular="1"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab [label=<<B>t2</B>>, shape="box" regular="1"];
  transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 [label=<<B>My custom transition label 1</B><BR/>color: Red<BR/>arrow_color: Green>, shape="box" regular="1"];
  transition_77de68daecd823babbb58edb1c8e14d7106e83bb [label=<<B>t4</B>>, shape="box" regular="1"];
  transition_1b6453892473a467d07372d45eb05abc2031647a [label=<<B>t5</B>>, shape="box" regular="1"];
  transition_ac3478d69a3c81fa62e60f5c3696165a4e5e6ac4 [label=<<B>t6</B>>, shape="box" regular="1"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [style="solid"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> transition_356a192b7913b04c54574d18c28d46e6395428ab [style="solid"];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 -> transition_356a192b7913b04c54574d18c28d46e6395428ab [style="solid"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab -> place_3c363836cf4e16666669a25da280a1865c2d2874 [style="solid"];
  place_3c363836cf4e16666669a25da280a1865c2d2874 -> transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 [style="solid"];
  transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 -> place_58e6b3a414a1e090dfc6029add0f3555ccba127f [style="solid"];
  place_3c363836cf4e16666669a25da280a1865c2d2874 -> transition_77de68daecd823babbb58edb1c8e14d7106e83bb [style="solid"];
  transition_77de68daecd823babbb58edb1c8e14d7106e83bb -> place_4a0a19218e082a343a1b17e5333409af9d98f0f5 [style="solid"];
  place_58e6b3a414a1e090dfc6029add0f3555ccba127f -> transition_1b6453892473a467d07372d45eb05abc2031647a [style="solid"];
  transition_1b6453892473a467d07372d45eb05abc2031647a -> place_54fd1711209fb1c0781092374132c66e79e2241b [style="solid"];
  place_4a0a19218e082a343a1b17e5333409af9d98f0f5 -> transition_ac3478d69a3c81fa62e60f5c3696165a4e5e6ac4 [style="solid"];
  transition_ac3478d69a3c81fa62e60f5c3696165a4e5e6ac4 -> place_54fd1711209fb1c0781092374132c66e79e2241b [style="solid"];
}
"""

SIMPLE_WORKFLOW_DUMP_WITHOUT_MARKING = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label=<<B>c</B>>, shape=circle style="filled" fillcolor="DeepSkyBlue"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [label=<<B>My custom transition label 2</B>>, shape="box" regular="1"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab [label=<<B>t2</B>>, shape="box" regular="1"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [style="solid"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> transition_356a192b7913b04c54574d18c28d46e6395428ab [style="solid"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab -> place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [style="solid"];
}
"""

SIMPLE_WORKFLOW_DUMP_WITHOUT_MARKING_WITH_METADATA = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label=<<B>c</B><BR/><I>My custom place description</I>>, shape=circle style="filled" fillcolor="DeepSkyBlue"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [label=<<B>My custom transition label 2</B><BR/>color: Grey<BR/>arrow_color: Purple>, shape="box" regular="1"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab [label=<<B>t2</B><BR/>arrow_color: Pink>, shape="box" regular="1"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [style="solid"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> transition_356a192b7913b04c54574d18c28d46e6395428ab [style="solid"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab -> place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [style="solid"];
}
"""

METADATA_EDGE_CASES_DUMP = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle style="filled" fillcolor="Orange"];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label=<<B>c</B><BR/><I>A &lt;bold&gt; description with &quot;special&quot; chars &amp; entities</I>>, shape=circle];
  place_3c363836cf4e16666669a25da280a1865c2d2874 [label=<<B>d</B><BR/><I>First line
Second line</I>>, shape=circle style="filled" fillcolor="Lime"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [label=<<B>t1</B>>, shape="box" regular="1"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab [label=<<B>t2</B>>, shape="box" regular="1"];
  transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 [label=<<B>t3</B><BR/><I>Transition description</I>>, shape="box" regular="1" style="filled" fillcolor="LightCoral"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [style="solid"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> transition_356a192b7913b04c54574d18c28d46e6395428ab [style="solid"];
  transition_356a192b7913b04c54574d18c28d46e6395428ab -> place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [style="solid"];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 -> transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 [style="solid"];
  transition_da4b9237bacccdf19c0760cab7aec4a8359010b0 -> place_3c363836cf4e16666669a25da280a1865c2d2874 [style="solid"];
}
"""


@pytest.mark.parametrize(
    ("definition", "expected", "with_metadata"),
    [
        pytest.param(
            create_complex_workflow_definition(),
            COMPLEX_WORKFLOW_DUMP_WITHOUT_MARKING,
            False,
            id="complex",
        ),
        pytest.param(
            create_simple_workflow_definition(),
            SIMPLE_WORKFLOW_DUMP_WITHOUT_MARKING,
            False,
            id="simple",
        ),
        pytest.param(
            create_complex_workflow_definition(),
            COMPLEX_WORKFLOW_DUMP_WITHOUT_MARKING_WITH_METADATA,
            True,
            id="complex-with-metadata",
        ),
        pytest.param(
            create_simple_workflow_definition(),
            SIMPLE_WORKFLOW_DUMP_WITHOUT_MARKING_WITH_METADATA,
            True,
            id="simple-with-metadata",
        ),
    ],
)
def test_dump_without_marking(definition: Definition, expected: str, with_metadata: bool) -> None:
    dump = GraphvizDumper().dump(definition, None, {"with-metadata": with_metadata})

    assert dump == expected


@pytest.mark.parametrize(
    ("definition", "marking", "expected", "with_metadata"),
    [
        pytest.param(
            create_complex_workflow_definition(),
            Marking({"b": 1}),
            COMPLEX_WORKFLOW_DUMP_WITH_MARKING,
            False,
            id="complex",
        ),
        pytest.param(
            create_simple_workflow_definition(),
            Marking({"c": 1, "d": 1}),
            SIMPLE_WORKFLOW_DUMP_WITH_MARKING,
            False,
            id="simple",
        ),
        pytest.param(
            create_complex_workflow_definition(),
            Marking({"b": 1}),
            COMPLEX_WORKFLOW_DUMP_WITH_MARKING_AND_METADATA,
            True,
            id="complex-with-metadata",
        ),
        pytest.param(
            create_simple_workflow_definition(),
            Marking({"c": 1, "d": 1}),
            SIMPLE_WORKFLOW_DUMP_WITH_MARKING_AND_METADATA,
            True,
            id="simple-with-metadata",
        ),
    ],
)
def test_dump_with_marking(
    definition: Definition, marking: Marking, expected: str, with_metadata: bool
) -> None:
    dump = GraphvizDumper().dump(definition, marking, {"with-metadata": with_metadata})

    assert dump == expected


def test_dump_escapes_special_characters_in_html_labels() -> None:
    transition_with_special_chars = Transition("t1", "a", "b")
    store = InMemoryMetadataStore(
        {},
        {"a": {"label": "A & B <tag>", "description": 'has "quotes" & <html>'}},
        {
            transition_with_special_chars: {
                "label": "Run <script>alert(1)</script>",
                "note": "a > b & c < d",
            }
        },
    )
    definition = Definition(["a", "b"], [transition_with_special_chars], None, store)

    dump = GraphvizDumper().dump(
        definition, None, {"with-metadata": True, "label": 'Title with <b>bold</b> & "quotes"'}
    )

    assert "<<B>A &amp; B &lt;tag&gt;</B>" in dump
    assert "<BR/><I>has &quot;quotes&quot; &amp; &lt;html&gt;</I>" in dump
    assert "<<B>Run &lt;script&gt;alert(1)&lt;/script&gt;</B>" in dump
    assert "note: a &gt; b &amp; c &lt; d" in dump
    assert "<<B>Title with &lt;b&gt;bold&lt;/b&gt; &amp; &quot;quotes&quot;</B>" in dump
    assert "<script>alert(1)</script>" not in dump
    assert "<tag>" not in dump


def test_dump_filters_workflow_level_metadata() -> None:
    store = InMemoryMetadataStore(
        {"bg_color": "Pink", "description": "Workflow description", "extra": "value"}
    )
    definition = Definition(["a", "b"], [Transition("t1", "a", "b")], None, store)

    dump = GraphvizDumper().dump(definition, None, {"with-metadata": True})

    assert "bg_color" not in dump
    assert "<BR/><I>Workflow description</I>" in dump
    assert "extra: value" in dump


def test_dump_filters_workflow_level_metadata_under_a_title() -> None:
    store = InMemoryMetadataStore(
        {"bg_color": "Pink", "description": "Workflow description", "extra": "value"}
    )
    definition = Definition(["a", "b"], [Transition("t1", "a", "b")], None, store)

    dump = GraphvizDumper().dump(definition, None, {"with-metadata": True, "label": "Title"})

    assert "bg_color" not in dump
    assert "<<B>Title</B>" in dump
    assert "<BR/><I>Workflow description</I>" in dump


def test_dump_with_listeners_folds_listeners_into_transition_metadata() -> None:
    definition = Definition(["a", "b"], [Transition("t1", "a", "b")])
    listeners = {
        "transition__0": {
            "workflow.wf.transition.t1": [
                {"title": "App\\Listener\\OnTransition::__invoke()", "file": None},
            ],
            "workflow.wf.guard.t1": [
                {
                    "title": "GuardListener",
                    "file": None,
                    "guardExpressions": ['is_granted("ROLE_USER")'],
                },
            ],
        },
    }

    dump = GraphvizDumper().dump(definition, None, {"listeners": listeners})

    assert "Listener #0: App\\Listener\\OnTransition::__invoke()" in dump
    assert "Listener #1: Guard: is_granted(&quot;ROLE_USER&quot;)" in dump


def test_dump_coerces_non_string_metadata_values_in_html_labels() -> None:
    transition = Transition("t1", "a", "b")
    store = InMemoryMetadataStore(
        {}, {}, {transition: {"count": 42, "ratio": 1.5, "tags": ["x", "y"], "empty": None}}
    )
    definition = Definition(["a", "b"], [transition], None, store)

    dump = GraphvizDumper().dump(definition, None, {"with-metadata": True})

    assert "count: 42" in dump
    assert "ratio: 1.5" in dump
    assert "tags: [&quot;x&quot;,&quot;y&quot;]" in dump


def test_dump_with_metadata_edge_cases() -> None:
    dump = GraphvizDumper().dump(
        create_workflow_with_metadata_edge_cases(), None, {"with-metadata": True}
    )

    assert dump == METADATA_EDGE_CASES_DUMP


NON_STRING_METADATA_DUMP = r"""digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [label=<<B>t1</B><BR/>flag_on: 1<BR/>flag_off: 0<BR/>nothing: <BR/>list: [&quot;a/b&quot;,&quot;é&quot;,&quot;x\u2028y&quot;,&quot;tab\t&quot;,true,null,1.5,2]<BR/>map: {&quot;k&quot;:&quot;v&quot;,&quot;n&quot;:[1,2.5]}<BR/>empty_list: []<BR/>empty_map: []<BR/>nested_empty: {&quot;e&quot;:[]}<BR/>whole: 2<BR/>quote: it&apos;s &quot;q&quot;<BR/>slash: a\b/c>, shape="box" regular="1"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [style="solid"];
}
"""


def test_dump_renders_every_kind_of_metadata_value() -> None:
    transition = Transition("t1", "a", "b")
    metadata: dict[str, object] = {
        "flag_on": True,
        "flag_off": False,
        "nothing": None,
        "list": ["a/b", "é", "x\u2028y", "tab\t", True, None, 1.5, 2.0],
        "map": {"k": "v", "n": [1, 2.5]},
        "empty_list": [],
        "empty_map": {},
        "nested_empty": {"e": {}},
        "whole": 2.0,
        "quote": 'it\'s "q"',
        "slash": "a\\b/c",
    }
    definition = Definition(
        ["a", "b"], [transition], None, InMemoryMetadataStore({}, {}, {transition: metadata})
    )

    dump = GraphvizDumper().dump(definition, None, {"with-metadata": True})

    assert dump == NON_STRING_METADATA_DUMP


LABEL_WITH_SLASHES_DUMP = r"""digraph workflow {
  ratio="compress" rankdir="LR" label="It\'s \"x\" \\ y"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
}
"""


def test_dump_escapes_quotes_and_backslashes_in_a_plain_title() -> None:
    dump = GraphvizDumper().dump(Definition(["a"], []), None, {"label": 'It\'s "x" \\ y'})

    assert dump == LABEL_WITH_SLASHES_DUMP


WEIGHTS_DUMP = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [label=<<B>t1</B>>, shape="box" regular="1"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [style="solid",label="2"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [style="solid",label="3"];
}
"""


def test_dump_labels_an_arc_weighing_more_than_one() -> None:
    definition = Definition(["a", "b"], [Transition("t1", [Arc("a", 2)], [Arc("b", 3)])])

    assert GraphvizDumper().dump(definition) == WEIGHTS_DUMP


OPTIONS_DUMP = """digraph workflow {
  ratio="compress" rankdir="TB" splines="ortho"
  node [fontsize="9" fontname="Arial" color="red" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
}
"""


def test_dump_merges_given_options_into_the_default_style() -> None:
    options = {"graph": {"rankdir": "TB", "splines": "ortho"}, "node": {"color": "red"}}

    dump = GraphvizDumper().dump(Definition(["a"], []), None, options)

    assert dump == OPTIONS_DUMP


def test_dump_leaves_the_default_style_unchanged() -> None:
    _ = GraphvizDumper().dump(Definition(["a"], []), None, {"node": {"color": "red"}})

    assert GraphvizDumper().dump(Definition(["a"], [])).count('color="#333333"') == 2


PLACE_LABEL_DUMP = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>Start</B>>, shape=circle style="filled" color="#FF0000" shape="doublecircle" fillcolor="Red"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>End</B>>, shape=circle];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [label=<<B>t1</B>>, shape="box" regular="1"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [style="solid"];
}
"""

PLACE_LABEL_WITH_METADATA_DUMP = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>Start</B><BR/>owner: me>, shape=circle style="filled" color="#FF0000" shape="doublecircle" fillcolor="Red"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>End</B>>, shape=circle];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [label=<<B>t1</B>>, shape="box" regular="1"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [style="solid"];
}
"""


@pytest.mark.parametrize(
    ("with_metadata", "expected"),
    [
        pytest.param(False, PLACE_LABEL_DUMP, id="without-metadata"),
        pytest.param(True, PLACE_LABEL_WITH_METADATA_DUMP, id="with-metadata"),
    ],
)
def test_dump_names_a_place_by_its_label(with_metadata: bool, expected: str) -> None:
    store = InMemoryMetadataStore(
        {}, {"a": {"label": "Start", "owner": "me", "bg_color": "Red"}, "b": {"label": "End"}}
    )
    definition = Definition(["a", "b"], [Transition("t1", "a", "b")], None, store)

    dump = GraphvizDumper().dump(definition, Marking({"a": 1}), {"with-metadata": with_metadata})

    assert dump == expected


_GRAPH_HEADER = '  ratio="compress" rankdir="LR"'


@pytest.mark.parametrize(
    ("workflow_metadata", "options", "graph_line"),
    [
        pytest.param(
            {"owner": "me", "team": "x"},
            {},
            f"{_GRAPH_HEADER} label=<owner: me<BR/>team: x>",
            id="metadata-only",
        ),
        pytest.param(
            {"description": "Desc"},
            {},
            f"{_GRAPH_HEADER} label=<<I>Desc</I>>",
            id="description-only",
        ),
        pytest.param(
            {"owner": "me", "description": "Desc"},
            {},
            f"{_GRAPH_HEADER} label=<owner: me<BR/><I>Desc</I>>",
            id="metadata-and-description",
        ),
        pytest.param({}, {}, _GRAPH_HEADER, id="nothing"),
        pytest.param(
            {"owner": "me"},
            {"label": "Title"},
            f"{_GRAPH_HEADER} label=<<B>Title</B><BR/>owner: me>",
            id="title-and-metadata",
        ),
    ],
)
def test_dump_labels_the_graph_from_the_workflow_metadata(
    workflow_metadata: dict[str, object], options: dict[str, object], graph_line: str
) -> None:
    definition = Definition(["a"], [], None, InMemoryMetadataStore(workflow_metadata))

    dump = GraphvizDumper().dump(definition, None, {"with-metadata": True, **options})

    assert dump == (
        "digraph workflow {\n"
        f"{graph_line}\n"
        '  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];\n'
        '  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];\n'
        "\n"
        '  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];\n'
        "}\n"
    )


LISTENERS_DUMP = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [label=<<B>t1</B><BR/>Listener #0: L1<BR/>Listener #1: Guard: a &amp;&amp; b>, shape="box" regular="1"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c [style="solid"];
  transition_b6589fc6ab0dc82cf12099d1c2d40ab994e8410c -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [style="solid"];
}
"""


def test_dump_numbers_listeners_across_events() -> None:
    listeners = {
        "transition__0": {
            "e1": [{"title": "L1"}],
            "e2": [{"title": "G", "guardExpressions": ["a", "b"]}],
        }
    }

    dump = GraphvizDumper().dump(
        Definition(["a", "b"], [Transition("t1", "a", "b")]), None, {"listeners": listeners}
    )

    assert dump == LISTENERS_DUMP
