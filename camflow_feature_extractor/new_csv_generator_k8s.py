import pandas as pd
import numpy as np
import json
import sys
import os

# global vars
EDGES = []
VERTICES = []
HEADER = ["bID_mID_oID", "object_type", "entity_path", "reader_path", "writer_path", "namespaces", "reader_relation_types", "writer_relation_types", "writer_argvs", "reader_argvs", "priviledged_flow", "CNS_event_count"]
ENTITY_COUNTS = {}
FEATURES = pd.DataFrame(columns=HEADER)
'''
HEADER:
    object_type             : (val) object type of center entity
    entity_path             : (list) paths associated to center entity
    reader_path             : (list) paths associated to readers of the center entity
    writer_path             : (list) paths associated to writers of the center entity
    namespaces              : (list) list of differing namespaces between readers and writers - [ipcns, mountns, netns, pidns, utsns] - if namespace differs = 1
    reader_relation_types   : (list) relation types of the readers of the the center entity
    writer_relation_types   : (list) relation types of the writers of the the center entity

    * center entity is the object on which the crossnamespace event is happening. There is only one center entity per json file.
'''
CENTER_ENTITY = None
VM_IPCNS = "4026531839"
CLUSTER_IPCNS = "4026532200"

# Adds center entity json obj to global variable
def set_center_entity(filepath):
    global VERTICES, CENTER_ENTITY

    # Extracting boot_id, machine_id, object_id.
    # input: "6_1851734740_22675_graph.json"
    # output [6,1851734740,22675]
    ids = filepath.split(".")[0].split("_")[:-1]
    ids[1] = "cf:" + ids[1]

    # updating center entity globally
    for v in VERTICES:
        if v["annotations"]["boot_id"] == ids[0] and v["annotations"]["cf:machine_id"] == ids[1] and v["annotations"]["object_id"] == ids[2]:
            CENTER_ENTITY = v


# Returns the object type of center entity
def extract_object_type():
    global CENTER_ENTITY

    object_type = ""

    try:
        object_type = CENTER_ENTITY["annotations"]["object_type"]
    except:
        pass

    return object_type

# Returns the paths associated to center entity
def extract_entity_path():
    global VERTICES, EDGES, CENTER_ENTITY

    paths = []

    ids_of_path_vertices = []

    for e in EDGES:
        # conditions
        from_center_entity = e["from"] == CENTER_ENTITY["id"]

        to_path_vertex = e["annotations"]["to_type"] == "path"

        # if edge is from center entity to path vertex
        if  from_center_entity and to_path_vertex:
            ids_of_path_vertices.append(e["to"])

    # Getting pathnames
    for v in VERTICES:
        if v["id"] in ids_of_path_vertices:
            paths.append(v["annotations"]["pathname"])


    return list(set(paths))

# Returns the paths associated to readers of the center entity
def extract_reader_path():
    global VERTICES, EDGES, CENTER_ENTITY

    paths = []

    # Getting ids of reading processes - type == Used
    ids_from_type_used = []

    for e in EDGES:
        # conditions
        to_center_entity = e["to"] == CENTER_ENTITY["id"]

        edge_type_used = e["type"] == "Used"

        if to_center_entity and edge_type_used:
            ids_from_type_used.append(e["from"])

    # Getting ids of process memories connected to all readers
    ids_of_process_memory_vertices = []

    for e in EDGES:
        # conditions
        from_process_memory_vertex = e["annotations"]["from_type"] == "process_memory"

        to_any_reader = e["to"] in ids_from_type_used

        if from_process_memory_vertex and to_any_reader:
            ids_of_process_memory_vertices.append(e["from"])

    # Getting ids of path vertices connected to process memories
    ids_of_path_vertices = []

    for e in EDGES:
        #conditions
        from_process_memory_vertex = e["from"] in ids_of_process_memory_vertices

        to_path_vertex = e["annotations"]["to_type"] == "path"

        if from_process_memory_vertex and to_path_vertex:
            ids_of_path_vertices.append(e["to"])

    # Getting pathnames
    for v in VERTICES:
        if v["id"] in ids_of_path_vertices:
            paths.append(v["annotations"]["pathname"])

    # In case of central entity being process memory, it is possible that the path of writers is same as central entity
    if paths == []:
        paths = extract_entity_path()

    return list(set(paths))

# Returns the paths associated to writers of the center entity
def extract_writer_path():
    global VERTICES, EDGES, CENTER_ENTITY

    paths = []

    # Getting ids of writing processes - type == WasGeneratedBy
    ids_to_type_WGB = []

    for e in EDGES:
        # conditions
        from_center_entity = e["from"] == CENTER_ENTITY["id"]

        edge_type_WGB = e["type"] == "WasGeneratedBy"

        if from_center_entity and edge_type_WGB:
            ids_to_type_WGB.append(e["to"])

    # Getting ids of process memories connected to all writers
    ids_of_process_memory_vertices = []

    for e in EDGES:
        # conditions
        to_process_memory_vertex = e["annotations"]["to_type"] == "process_memory"

        from_any_writer = e["from"] in ids_to_type_WGB

        if to_process_memory_vertex and from_any_writer:
            ids_of_process_memory_vertices.append(e["to"])

    # Getting ids of path vertices connected to process memories
    ids_of_path_vertices = []

    for e in EDGES:
        #conditions
        from_process_memory_vertex = e["from"] in ids_of_process_memory_vertices

        to_path_vertex = e["annotations"]["to_type"] == "path"

        if from_process_memory_vertex and to_path_vertex:
            ids_of_path_vertices.append(e["to"])

    # Getting pathnames
    for v in VERTICES:
        if v["id"] in ids_of_path_vertices:
            paths.append(v["annotations"]["pathname"])

    # In case of central entity being process memory, it is possible that the path of writers is same as central entity
    if paths == []:
        paths = extract_entity_path()

    return list(set(paths))

# Returns the list of differing namespaces between readers and writers
# ipcns, mountns, netns, pidns, utsns
def extract_namespaces():
    global VERTICES, EDGES, CENTER_ENTITY

    #contains a list of the tuples of namespaces
    reader_ns = (set(), set(), set(), set(), set())
    writer_ns = (set(), set(), set(), set(), set())

    # Getting ids of reading processes - type == Used
    ids_from_type_used = []
    # Getting ids of writing processes - type == WasGeneratedBy
    ids_to_type_WGB = []

    for e in EDGES:
        # conditions
        to_center_entity = e["to"] == CENTER_ENTITY["id"]

        edge_type_used = e["type"] == "Used"

        if to_center_entity and edge_type_used:
            ids_from_type_used.append(e["from"])

        from_center_entity = e["from"] == CENTER_ENTITY["id"]

        edge_type_WGB = e["type"] == "WasGeneratedBy"

        if from_center_entity and edge_type_WGB:
            ids_to_type_WGB.append(e["to"])

    for v in VERTICES:
        for id in ids_from_type_used:
            if (v['id'] == id):
                r_ns = (v['annotations']['ipcns'], v['annotations']['mntns'], v['annotations']['netns'], v['annotations']['pidns'], v['annotations']['utsns'])

                for i in range (5):
                    reader_ns[i].add(r_ns[i])

        for id in ids_to_type_WGB:
            if (v['id'] == id):
                w_ns = (v['annotations']['ipcns'], v['annotations']['mntns'], v['annotations']['netns'], v['annotations']['pidns'], v['annotations']['utsns'])

                for i in range (5):
                        writer_ns[i].add(w_ns[i])

    one_hot = [0, 0, 0, 0, 0]

    for i in range (5):
       diff = reader_ns[i].symmetric_difference(writer_ns[i])

       if len(diff) != 0:
           one_hot[i] = 1

    return one_hot

def extract_priviledge_flow():
    global VERTICES, EDGES, CENTER_ENTITY, VM_IPCNS, CLUSTER_IPCNS

    #contains a list of the tuples of namespaces
    reader_ns = (set(), set(), set(), set(), set())
    writer_ns = (set(), set(), set(), set(), set())
    reader_i_p_ns = set()
    writer_i_p_ns = set()

    # Getting ids of reading processes - type == Used
    ids_from_type_used = []
    # Getting ids of writing processes - type == WasGeneratedBy
    ids_to_type_WGB = []

    for e in EDGES:
        # conditions
        to_center_entity = e["to"] == CENTER_ENTITY["id"]

        edge_type_used = e["type"] == "Used"

        if to_center_entity and edge_type_used:
            ids_from_type_used.append(e["from"])

        from_center_entity = e["from"] == CENTER_ENTITY["id"]

        edge_type_WGB = e["type"] == "WasGeneratedBy"

        if from_center_entity and edge_type_WGB:
            ids_to_type_WGB.append(e["to"])

    for v in VERTICES:
        for id in ids_from_type_used:
            if (v['id'] == id):
                r_ns = (v['annotations']['ipcns'], v['annotations']['mntns'], v['annotations']['netns'], v['annotations']['pidns'], v['annotations']['utsns'])
                reader_i_p_ns.add((v['annotations']['ipcns'], v['annotations']['pidns']))
                for i in range (5):
                    reader_ns[i].add(r_ns[i])

        for id in ids_to_type_WGB:
            if (v['id'] == id):
                w_ns = (v['annotations']['ipcns'], v['annotations']['mntns'], v['annotations']['netns'], v['annotations']['pidns'], v['annotations']['utsns'])
                writer_i_p_ns.add((v['annotations']['ipcns'], v['annotations']['pidns']))
                for i in range (5):
                        writer_ns[i].add(w_ns[i])

    # check_writer_container = False
    # check_reader_host = False

    # for ns in writer_ns[0]:
    #     if ns != HOST_IPCNS:
    #         check_writer_container = True

    # for ns in reader_ns[0]:
    #     if ns == HOST_IPCNS:
    #         check_reader_host = True

    priviledged_flow = 0
    read_from_vm = False
    write_from_cluster = False
    write_from_vm = False
    read_from_cluster = False
    write_from_pod = False
    writer_pod_ns = set()
    reader_pod_ns = set()

    # Only a write from VM 
    if (len(writer_ns[0]) == 1) and (VM_IPCNS in writer_ns[0]):
        priviledged_flow = 0
    else:
        for ns in writer_ns[0]:
            if ns == CLUSTER_IPCNS:
                write_from_cluster = True
            elif ns == VM_IPCNS:
                write_from_vm = True
            else:
                write_from_pod = True
        
        for ns in reader_ns[0]:
            if ns == VM_IPCNS:
                read_from_vm = True
            elif ns == CLUSTER_IPCNS:
                read_from_cluster = True

        if write_from_cluster and read_from_vm:
            priviledged_flow = 1
        
        if write_from_pod and read_from_vm:
            priviledged_flow = 1
        
        if write_from_pod and read_from_cluster:
            priviledged_flow = 1
        
        if write_from_pod:

            ## Exttacting only the pod (ipcns, pid) sets from reader and writer
            to_del = []
            for x in writer_i_p_ns:
                if x[0] == CLUSTER_IPCNS or x[0] == VM_IPCNS:
                    to_del.append(x)
            for x in to_del:
                writer_i_p_ns.remove(x)
            
            to_del = []
            for x in reader_i_p_ns:
                if x[0] == CLUSTER_IPCNS or x[0] == VM_IPCNS:
                    to_del.append(x)
            for x in to_del:
                reader_i_p_ns.remove(x)
            
            # checking if there exists a reader which differs from pod ns and vice versa
            for x in reader_i_p_ns:
                if x not in writer_i_p_ns:
                    priviledged_flow = 1
                    break
            
    

    return priviledged_flow


# Returns the relation types of the readers of the the center entity
def extract_reader_relation_types():
    global VERTICES, EDGES, CENTER_ENTITY

    # Getting ids of reading processes - type == Used
    reader_relation_types = []

    for e in EDGES:
        # conditions
        to_center_entity = e["to"] == CENTER_ENTITY["id"]

        edge_type_used = e["type"] == "Used"

        if to_center_entity and edge_type_used:
            reader_relation_types.append(e["annotations"]["relation_type"])


    return list(set(reader_relation_types))

# Returns the relation types of the writers of the the center entity
def extract_writer_relation_types():
    global VERTICES, EDGES, CENTER_ENTITY

    # Getting ids of writing processes - type == WasGeneratedBy
    writer_relation_types = []

    for e in EDGES:
        # conditions
        from_center_entity = e["from"] == CENTER_ENTITY["id"]

        edge_type_WGB = e["type"] == "WasGeneratedBy"

        if from_center_entity and edge_type_WGB:
            writer_relation_types.append(e["annotations"]["relation_type"])

    return list(set(writer_relation_types))

def extract_writer_argvs():
    global VERTICES, EDGES, CENTER_ENTITY

    argvs = []

    # Getting ids of writing processes - type == WasGeneratedBy 
    ids_to_type_WGB = []

    for e in EDGES:
        # conditions
        from_center_entity = e["from"] == CENTER_ENTITY["id"]

        edge_type_WGB = e["type"] == "WasGeneratedBy"

        if from_center_entity and edge_type_WGB:
            ids_to_type_WGB.append(e["to"])

    # Getting ids of process memories connected to all writers
    ids_of_process_memory_vertices = []

    for e in EDGES:
        # conditions
        to_process_memory_vertex = e["annotations"]["to_type"] == "process_memory"

        from_any_writer = e["from"] in ids_to_type_WGB

        if to_process_memory_vertex and from_any_writer:
            ids_of_process_memory_vertices.append(e["to"])

    # Getting ids of argv vertices connected to process memories
    ids_of_argv_vertices = []

    for e in EDGES:
        #conditions
        from_process_memory_vertex = e["from"] in ids_of_process_memory_vertices

        to_path_vertex = e["annotations"]["to_type"] == "argv"

        if from_process_memory_vertex and to_path_vertex:
            ids_of_argv_vertices.append(e["to"])

    # Getting values of argvs
    for v in VERTICES:
        if v["id"] in ids_of_argv_vertices:
            try: 
                argvs.append(v["annotations"]["value"])
            except:
                pass

    # In case of central entity being process memory, it is possible that the path of writers is same as central entity
    # if paths == []:
    #     paths = extract_entity_path()

    argvs = list(set(argvs))
    return argvs

def extract_reader_argvs():
    global VERTICES, EDGES, CENTER_ENTITY

    argvs = []

    # Getting ids of reading processes - type == Used 
    ids_from_type_used = []

    for e in EDGES:
        # conditions
        to_center_entity = e["to"] == CENTER_ENTITY["id"]

        edge_type_used = e["type"] == "Used"

        if to_center_entity and edge_type_used:
            ids_from_type_used.append(e["from"])

    # Getting ids of process memories connected to all readers
    ids_of_process_memory_vertices = []

    for e in EDGES:
        # conditions
        from_process_memory_vertex = e["annotations"]["from_type"] == "process_memory"

        to_any_reader = e["to"] in ids_from_type_used

        if from_process_memory_vertex and to_any_reader:
            ids_of_process_memory_vertices.append(e["from"])

    # Getting ids of argv vertices connected to process memories
    ids_of_argv_vertices = []

    for e in EDGES:
        #conditions
        from_process_memory_vertex = e["from"] in ids_of_process_memory_vertices

        to_path_vertex = e["annotations"]["to_type"] == "argv"

        if from_process_memory_vertex and to_path_vertex:
            ids_of_argv_vertices.append(e["to"])

    # Getting pathnames
    for v in VERTICES:
        if v["id"] in ids_of_argv_vertices:
            try:
                argvs.append(v["annotations"]["value"])
            except:
                pass

    # # In case of central entity being process memory, it is possible that the path of writers is same as central entity
    # if paths == []:
    #     paths = extract_entity_path()

    argvs = list(set(argvs))
    return argvs

def load_data(filepath):
    global EDGES, VERTICES
    
    print("Reading json file:", filepath)

    with open(filepath, "r") as f:
        for line in f:
            if "[" in line or "]" in line:
                continue

            if line[0] == ",":
                obj = json.loads(line[1:])
            else:
                obj = json.loads(line)

            if "from_type" in obj["annotations"]:
                EDGES.append(obj)
            else:
                VERTICES.append(obj)

    print("Done")

def calculate_entity_counts(cns_json_path):
    global ENTITY_COUNTS

    fd = open(cns_json_path, 'r')

    for line in fd:
        obj = json.loads(line)

        curr_entity = obj['artifact']['boot_id'] + "_" + obj['artifact']['cf:machine_id'].split(":")[1] + "_" + obj['artifact']['object_id']
        if curr_entity not in ENTITY_COUNTS:
            ENTITY_COUNTS[curr_entity] = 1
        else:
            ENTITY_COUNTS[curr_entity] = ENTITY_COUNTS[curr_entity] + 1

def extract_identifier(filepath):
    splitted_filepath = filepath.split("_")
    return_str = splitted_filepath[0] + "_" + splitted_filepath[1] + "_" + splitted_filepath[2]
    return return_str

def extract_cns_event_count(bID_mID_oID):
    global ENTITY_COUNTS
    return ENTITY_COUNTS[bID_mID_oID]

def main(filepath, cns_json_path):
    global EDGES, VERTICES, FEATURES, VM_IPCNS, CLUSTER_IPCNS

    calculate_entity_counts(cns_json_path)

    files = []

    with open(filepath, "r") as f:
        files = f.readlines()

    counter = 1
    for file in files:
        load_data(file.strip())

        set_center_entity(file.strip())

        object_type = extract_object_type()
        entity_path = extract_entity_path()
        reader_path = extract_reader_path()
        writer_path = extract_writer_path()
        namespaces  = extract_namespaces()
        reader_relation_types = extract_reader_relation_types()
        writer_relation_types = extract_writer_relation_types()
        writer_argvs = extract_writer_argvs()
        reader_argvs = extract_reader_argvs()
        priviledged_flow = extract_priviledge_flow()
        bID_mID_oID = extract_identifier(file)
        cns_event_count = extract_cns_event_count(bID_mID_oID)

        data_point = {HEADER[0]: bID_mID_oID,
                    HEADER[1]: object_type, 
                    HEADER[2]: entity_path, 
                    HEADER[3]: reader_path, 
                    HEADER[4]: writer_path, 
                    HEADER[5]: namespaces, 
                    HEADER[6]: reader_relation_types, 
                    HEADER[7]: writer_relation_types,
                    HEADER[8]: writer_argvs,
                    HEADER[9]: reader_argvs,
                    HEADER[10]: priviledged_flow,
                    HEADER[11]: cns_event_count
                    }
        
        FEATURES = FEATURES.append(data_point, ignore_index = True)

        #print(FEATURES)
        print("********** " + str(counter) + " JSON file(s) processed **********\n")
        counter = counter+ 1

    FEATURES.to_csv("features.csv", index=False)


if __name__ == '__main__':
    try:
        if len(sys.argv) != 3:
            raise Exception("run python3 csv_generator.py <filepath> <cns_json_path>")
        else:
            print("Starting...")
            print("Filepath:", sys.argv[1])
            print("CNS Json Path:", sys.argv[2])
            # print("Host IPCNS:", sys.argv[2])
            main(sys.argv[1], sys.argv[2])
        
    except KeyboardInterrupt:
        print("Exiting...")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
