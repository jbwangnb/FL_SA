import random

from client import *
import datasets
from CA import GraphStruct

if __name__ == '__main__':

    # 设置命令行程序
    # parser = argparse.ArgumentParser(description='Federated Learning')
    # parser.add_argument('-c', '--conf', dest='conf')
    # 获取所有的参数
    # args = parser.parse_args()

    # 读取配置文件
    # with open(args.conf, 'r') as f:
    with open("./utils/conf.json", 'r') as f:
        # 加载json文件
        conf = json.load(f)

    train_datasets, eval_datasets = datasets.get_dataset("./data/", conf["type"])

    # 开启服务器
    server = Server(conf, eval_datasets)

    # 客户端列表
    clients = []

    # 添加10个客户端
    for c in range(conf["no_models"]):
        clients.append(Client(conf, server.global_model, train_datasets, c))

    # 生成图
    generate_graph = GraphStruct()

    # 全局模型训练，全局迭代次数 conf["global_epochs"]
    for e in range(conf["global_epochs"]):
        print("Global Epoch %d" % e)
        # 每次训练都是从clients列表中随机采样k个进行本轮训练
        candidates = random.sample(clients, conf["k"])
        generate_graph.node_number = len(candidates)
        candidates_dict = {}
        for c in candidates:
            candidates_dict[c.client_id] = c
            c.client_list = candidates

        # 每个客户端把通信时延传给CA
        communication_cost = c.compute_communication_cost()
        for c in candidates:
            generate_graph.communication_cost(communication_cost)
        # 求解局部连接图(最小生成树)
        generate_graph.init_graph(candidates)

        # wait... 当CA将最小生成树返回给各个客户端和服务器时，继续执行
        for c in candidates:
            c.part_connect_graph = generate_graph.part_connect_graph
        server.part_connect_graph = generate_graph.part_connect_graph

        weight_accumulator = {}

        # torch.nn.Module模块中的state_dict变量存放训练过程中需要学习的权重和偏执系数，
        # state_dict作为python的字典对象将每一层的参数映射成tensor张量
        for name, params in server.global_model.state_dict().items():
            # 生成一个和参数矩阵大小相同的0矩阵
            weight_accumulator[name] = torch.zeros_like(params)

        # t-out-of-n 分发bu和密钥



        # 遍历客户端，每个客户端本地训练模型 加掩码mask
        for c in candidates:
            diff = c.local_train(server.global_model)
            # mask
            shared_keys = {}
            for client1, client2, cost in c.part_connect_graph:
                if int(client1) == c.client_id:
                    shared_keys[client2] = candidates_dict[client2].sec_agg.public_key()
                if int(client2) == c.client_id:
                    shared_keys[client1] = candidates_dict[client1].sec_agg.public_key()
            for name in diff:
                item = diff[name].detach().numpy()
                dim = item.shape
                c.sec_agg.set_weights(diff, dim)
                c.sec_agg.prepare_weights(shared_keys, c.client_id)
            # 模型反演攻击
            # ...


            # 根据客户端的参数差值字典更新总体权重
            for name, params in server.global_model.state_dict().items():
                weight_accumulator[name].add_(diff[name])
                # print(name)
                # print(weight_accumulator[name])

        # client_socket.send(weight_accumulator)

        # 模型参数聚合
        # print(weight_accumulator)
        # for name, params in server.global_model.state_dict().items():
        #     print(name)
        #     print(params)
        server.model_aggregate(weight_accumulator)
        # 模型评估
        for name, params in server.global_model.state_dict().items():
            print(name)
            print(params)
        acc, loss = server.model_eval()
        print("Global Epoch %d, acc: %f, loss: %f\n" % (e, acc, loss))

# for name, params in server.global_model.state_dict().items():
#     print(name)
#     print(params)
#     np_param = params.detach().numpy()
#     print(np_param)
