
import hashlib #提供字符加密功能
import json
from time import time
from uuid import uuid4 #基于随机数生成UUID
from flask import Flask,jsonify,request 
from urllib.parse import urlparse  
from argparse import ArgumentParser #解析命令行参数
import requests  #HTTP库，可完成浏览器可有的任何操作


#Blockchain类负责管理链式数据：提供存储交易和添加新的区块到链的方法
class Blockchain(object):
    def __init__(self):
        self.chain=[]  #存储区块链
        self.current_transactions=[]   #此列表用于记录目前在区块链网络中已经经矿工确认合法的交易信息，等待写入新区块中的交易信息
        self.nodes=set()  #建立一个无序元素集合。此集合用于存储区块链网络中已发现的所有节点信息
        #创建创世区块
        self.new_block(previous_hash=1,proof=100)

    
    # 注册节点
    def register_node(self, address):
        """
        在节点列表中增加一个节点
        :param address: 地址节点. Eg. 'http://192.168.0.5:5000'
        """
        # 检查节点的格式，通过urlparse方法将这个节点的url分割成六个部分
        parsed_url = urlparse(address)
        # 如果网络地址不为空，那么就添加没有http://之类修饰的纯的地址，如：www.baidu.com
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)
        # 如果网络地址为空，那么就添加相对Url的路径
        elif parsed_url.path:
            # Accepts an URL without scheme like '192.168.0.5:5000'.
            self.nodes.add(parsed_url.path)
        else:
            raise ValueError('Invalid URL')  # 说明这是一个非标准的Url

    # 验证区块链有效性（检查bockchain是否有效，即检查是否每个区块都合法）
    def valid_chain(self, chain):
        """
        确定区块链是否合法
        :param chain: A blockchain
        :return: 合法返回True,否则返回False
        """
        # 这里取得的是创世区块，因为必须从头检查整个区块链上从创世区块到链上最后一个区块为止的所有区块的链接关系
        last_block = chain[0]

        # 下面的while循环就是为了检查链上每一个区块与其连接的前一个区块是否合法相关，通过 检查 previous_hash 来判断
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")
            last_block_hash = self.hash(last_block)

            # 检查块的哈希是否正确
            if block['previous_hash'] != last_block_hash:
                return False  # 如果发现当前在检查的区块的previous_hash值与它实际连接的前一区块的hash值不同，则证明此链条有问题，终止检查

            # 检查工作量证明是否正确
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block  # 让当前区块变成前一个区块，以迭代到一下次循环
            current_index += 1  # 让下一个区块区区块号+1

        return True
        
    # 解决冲突
    def resolve_conflicts(self):
        """
        解决区块链节点之间的冲突，用网络中最长的链替换我们的链。
        :return: True if our chain was replaced, False if not
        """
        neighbours = self.nodes
        new_chain = None
        # 本节点的存储的区块链条的长度（即有多少 个区块）
        max_length = len(self.chain)
        # 获取所有已知区块链网络中的节点中存储的区块链条，并分析其是否比本节点的链条长度要长
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')  # 到每个节点的chain页面去获取此节点的区块链条信息，返回结果包含了一个chain对象本身和它的长度信息
            # HTTP状态码等于200表示请求成功
            if response.status_code == 200:
                length = response.json()['length']  # 通过json类把返回的对象取出来
                chain = response.json()['chain']
                # 如果此节点的区块链长度比本节点区块链长度长，且链条合法，则证明是值得覆盖本节点链条的合法链条
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain
        # 用找到的比本节点区块链链条长的链条覆盖本节点的旧链条
        if new_chain:
            self.chain = new_chain
            return True
        return False   # 如果没有发现别的节点上的链条比本节点的链条更长，那么 就返回 FALSE

    def new_block(self,proof,previous_hash=None):
        #创造新的块并将它加入到链中
        '''
        param proof:<int>由工作证明算法生成的证明
        param previous_hash:(optional)<str>前一个区块的hash值
        return:<dict>新区块
        '''
        block={
            'index':len(self.chain)+1,#区块编号
            'timestamp':time(),#时间戳
            'transactions':self.current_transactions,#交易信息
            'proof':proof,#矿工通过算力证明（工作量证明）成功得到的Number Once值，证明其合法创建了一个区块（当前区块）
            'previous_hash':previous_hash or self.hash(self.chain[-1]),#前一个区块的哈希值
            }

        #重置当前交易记录:因为已经将待处理交易信息列表中的所有交易信息写入区块并添加到区块链末尾，因此需要清除列表中的内容
        self.current_transactions=[]
        #将当前区块添加到区块链末端
        self.chain.append(block)
        return block

    def new_transaction(self,sender,recipient,amount):
        #在交易列表增加新的交易
        """
        创建一个进入下一个开采区块的新交易
        :param sender: <str> 发送者地址
        :param recipient: <str> 接收者地址
        :param amount: <int> 数额
        :return: <int> 交易将被添加到的块的索引
        """
        self.current_transactions.append({
            'sender':sender,
            'recipient':recipient,
            'amount':amount,
            })

        #下一个待挖的区块中
        return self.last_block['index']+1

    #返回区块链中最新区块
    @property
    def last_block(self):
        return self.chain[-1]

    #给一个区块生成哈希值
    @staticmethod
    def hash(block):
        '''
        通过json.dumps方法将一个区块打散并进行排序，保证每一次对于同一个区块都是同样的排序
        将其转换为json编码格式，再用encode()方法进行编码处理，默认编码'utf-8'
        最后hexigest()以16进制输出
        param block:<dict> Block
        return:<str>
        '''
        block_string=json.dumps(block,sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()
   
   #实现一个类似Pow   Pow(工作量证明)：证明如何在区块链上创建或挖掘新的区块。其核心思想是找出一个符合特定条件的数字，这个数字很难被计算，但容易被证明
    def proof_of_work(self,last_proof):
        '''
        设定工作量证明:
        查找一个p'，使得hash(pp')以4个0开头，其中p是上一个块的证明，p'是当前的证明        
        :param last_proof: <int>
        :return: <int>
        '''
        proof=0
        #通过循环从0开始找到一个符合算法要求的proof值
        while self.valid_proof(last_proof,proof) is False:
            proof+=1   

        return proof

    @staticmethod
    def valid_proof(last_proof,proof):
        '''
        该函数用于辅助上一个函数
        检测哈希值是否满足条件--即hash(last_proof,proof)是否以4个0开头
        :param last_proof: <int> Previous Proof
        :param proof: <int> Current Proof
        :return: <bool> True if correct, False if not.
        '''

        #根据传入的proof进行尝试运算，得到一个utf-8格式的字符串
        guess=f'{last_proof}{proof}'.encode()
        #将字符串以sha356加密，并转为16进制
        guess_hash=hashlib.sha256(guess).hexdigest()
        #验证前4位是否为0，符合返回True，否则返回False
        return guess_hash[:4]=='0000'

#实例化节点：加载Flask框架
app=Flask(__name__)

#随机创建节点名称
node_identifier=str(uuid4()).replace('-','')

#实例化Blockchain类
blockchain=Blockchain()

#创建/transactions/new接口端点，设置为POST请求来给接口发送交易数据
@app.route('/transactions/new',methods=['POST'])
def new_transaction():
    #对参数进行处理，得到字典格式，因此排序会打乱依据字典排序规则
    #get_json()默认对minetype为application/json的请求可以正确解析，并将数据作为json输出，如果不是则返回None 解决办法:将get_json()参数force改为True，则会忽略minetype并始终尝试解析json
    values=request.get_json()

    #检查所需字段是否存在
    required=['sender','recipient','amount']
    if not all(k in values for k in required):
        return 'Missing values',400      #HTTP状态码400，请求错误

    #创建新交易
    index=blockchain.new_transaction(values['sender'],values['recipient'],values['amount'])
    response={'message':f'Transaction will be added to Block{index}'}
    return jsonify(response),201

#创建mine端点，设置为GET请求
@app.route('/mine',methods=['GET'])
def mine():
    #运行工作算法获得下一个证明
    last_block=blockchain.last_block  #取出当前区块链最后一个区块
    last_proof=last_block['proof']    #取出最后一个区块的哈希值
    proof=blockchain.proof_of_work(last_proof)  #获得一个可以优先创建下一个区块的工作量证明的proof值

    #sender为0表示此节点挖掘到了一个新货币
    blockchain.new_transaction(
        sender='0',
        recipient=node_identifier,
        amount=1,
    )

    #将新区块添加到链中
    previous_hash=blockchain.hash(last_block)  #取出区块链最长链的最后一个区块的Hash值，用于要新加区块的前导Hash值，以此实现连接
    block=blockchain.new_block(proof,previous_hash)  #将新区快添加到链的最后

    response={
        'message':'New Block Forged',
        'index':block['index'],
        'transactions':block['transactions'],
        'proof':block['proof'],
        'previous_hash':block['previous_hash'],
        }

    return jsonify(response),200

#创建/chain端点，用来返回整个Blockchain类
@app.route('/chain',methods=['GET'])
# 将返回本节点存储的区块链条的完整信息和长度信息
def full_chain():
    response = {
        'chain':blockchain.chain,
        'length':len(blockchain.chain),
    }
    return jsonify(response),200


# 注册节点 
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400
    for node in nodes:
        blockchain.register_node(node)
    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

# 添加节点解决冲突的路由
@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    # 解决多个区块链网络节点间的节点冲突，更新为区块链网络中最长的那条链条-
    replaced = blockchain.resolve_conflicts()
    # 如果使用的本节点的链条，那么返回如下
    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    # 如果更新别的节点的链条，那么返回如下：
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }
    return jsonify(response), 200  # jsonify()序列化把返回信息变成字符


if __name__ == '__main__':
    parser = ArgumentParser()  # 创建一个参数接收的解释器，由对象parser负责解释参数信息
    parser.add_argument('-p', '--port', default=5001, type=int, help='port to listen on')
    args = parser.parse_args()  # 通过parse_args()方法尝试对收到的参数关键字进行解释
    port = args.port  # 从args对象中取出其中的参数关键字--port 参数的内容，也可能是获取到预设的默认值
    app.run(host='0.0.0.0', port=port)
