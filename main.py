import os
import sys
import pandas as pd
import pm4py
from pm4py.objects.conversion.process_tree import converter
from pm4py.visualization.process_tree import visualizer as pt_visualizer

from pipeline_runner_igraph import run_pipeline_multi_layer_igraph

folder_index = int(sys.argv[1])
directory = sys.argv[2]


def import_csv(file_path):
    event_log = pd.read_csv(file_path, sep=';')
    num_events = len(event_log)
    num_cases = len(event_log.case_id.unique())
    print("Number of events: {}\nNumber of cases: {}".format(num_events, num_cases))


def main() -> None:
    input_paths = []
    for folder_name in (os.listdir(directory)):
        input_paths.append((os.path.join(directory, folder_name, 'logs/'), folder_name))

    run_pipeline_multi_layer_igraph([input_paths[folder_index]])
    return

def export_bpmn_model(log):
    tree = pm4py.discover_process_tree_inductive(log)
    bpmn_graph = converter.apply(tree, variant=converter.Variants.TO_BPMN)
    pm4py.write_bpmn(bpmn_graph, '/home/jonas/repositories/pm-label-splitting/test_files/test.bpmn', enable_layout=True)
    gviz = pt_visualizer.apply(tree)
    pt_visualizer.view(gviz)


main()
