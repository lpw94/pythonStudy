"""名人候选表。

为什么需要「候选表」
------------------
CLIP 是**零样本**模型：它只能在「你给它的这些名字」里排序，
没法凭空说出一个人是谁。所以候选表就是模型的输出空间。

为什么每个名字要配中英文
------------------------
CLIP 的文本编码器是在英文图文对上训练的，对英文人名的理解远好于中文名。
「成龙」在它的世界里几乎没有对应，「Jackie Chan」则非常强。
所以：**用英文名去做模型匹配，中文名只用于展示给人看**。

这不是「翻译一下」，而是**为模型选它最擅长的那个表述**。
中文明星尤其明显 —— 直接用中文名匹配，准确率会显著下降。

如何扩展
--------
内置表只是「开箱能用」的起点。把自定义人选追加到
``models/candidates.txt``（每行 ``中文名|英文名`` 或 ``英文名``）即可，
不需要改代码。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Candidate:
    """一个待识别的名人。

    Attributes:
        zh: 中文名（用于展示）。
        en: 英文名（用于与 CLIP 文本特征匹配）。
        aliases: 别名/艺名/代表角色（同样参与匹配）。

    为什么需要别名
    --------------
    实测踩出来的坑：CLIP 对明星的认知来自网络图文对，
    而网络上**艺名和角色名的出现频率远高于本名**：

    - Dwayne Johnson → CLIP 认的是「The Rock」
    - Hugh Jackman → CLIP 认的是「Wolverine」
    - Emma Watson → CLIP 认的是「Hermione Granger」

    只用本名匹配，这三个人一个都认不出来（实测各 10 张全错）。
    加上别名之后，同一张图取「本名 / 别名」里的最高分即可。
    """

    zh: str
    en: str
    aliases: tuple[str, ...] = ()

    @property
    def display(self) -> str:
        """展示用名称：中英文都有时用「中文名（英文名）」。"""
        if self.zh and self.en and self.zh != self.en:
            return f"{self.zh}（{self.en}）"
        return self.zh or self.en

    @property
    def variants(self) -> tuple[str, ...]:
        """所有参与匹配的文本表述（本名 + 别名）。"""
        return (self.en, *self.aliases)

    @classmethod
    def parse(cls, line: str) -> Candidate | None:
        """从一行文本解析候选。

        格式：``中文名|英文名`` 或 ``中文名|英文名|别名1,别名2``。
        也支持只有英文名的写法 ``英文名``。

        Args:
            line: 原始行。

        Returns:
            候选对象；行无效时返回 None。
        """
        line = line.strip()
        if not line or line.startswith("#"):
            return None

        if "|" in line:
            parts = line.split("|")
            zh = parts[0].strip()
            en = parts[1].strip() if len(parts) > 1 else ""
            alias_text = parts[2] if len(parts) > 2 else ""
        else:
            zh, en, alias_text = "", line, ""

        if not en:
            return None

        aliases = tuple(a.strip() for a in alias_text.split(",") if a.strip())
        return cls(zh=zh, en=en, aliases=aliases)


# 内置候选表：华语 + 港台 + 日韩 + 好莱坞，覆盖「拿张剧照就想认人」的高频场景。
BUILTIN_CANDIDATES: tuple[Candidate, ...] = (
    # ---------- 华语圈 ----------
    Candidate("成龙", "Jackie Chan", aliases=("Kung Fu",)),
    Candidate("李小龙", "Bruce Lee"),
    Candidate("周润发", "Chow Yun-fat"),
    Candidate("周星驰", "Stephen Chow"),
    Candidate("刘德华", "Andy Lau"),
    Candidate("梁朝伟", "Tony Leung Chiu-wai"),
    Candidate("张国荣", "Leslie Cheung"),
    Candidate("梅艳芳", "Anita Mui"),
    Candidate("邓丽君", "Teresa Teng"),
    Candidate("王菲", "Faye Wong"),
    Candidate("那英", "Na Ying"),
    Candidate("韩红", "Han Hong"),
    Candidate("薛之谦", "Joker Xue"),
    Candidate("周杰伦", "Jay Chou"),
    Candidate("林俊杰", "JJ Lin"),
    Candidate("陈奕迅", "Eason Chan"),
    Candidate("张学友", "Jacky Cheung"),
    Candidate("黎明", "Leon Lai"),
    Candidate("郭富城", "Aaron Kwok"),
    Candidate("张靓颖", "Jane Zhang"),
    Candidate("邓紫棋", "G.E.M."),
    Candidate("毛不易", "Mao Buyi"),
    Candidate("李荣浩", "Li Ronghao"),
    Candidate("张艺兴", "Lay Zhang", aliases=("Zhang Yixing",)),
    Candidate("鹿晗", "Lu Han"),
    Candidate("吴亦凡", "Kris Wu"),
    Candidate("李易峰", "Li Yifeng"),
    Candidate("肖战", "Xiao Zhan", aliases=("Xiao Zhan",)),
    Candidate("王一博", "Wang Yibo"),
    Candidate("杨洋", "Yang Yang"),
    Candidate("迪丽热巴", "Dilraba Dilmurat"),
    Candidate("杨幂", "Yang Mi"),
    Candidate("赵丽颖", "Zhao Liying"),
    Candidate("刘亦菲", "Liu Yifei"),
    Candidate("杨紫", "Yang Zi"),
    Candidate("白百何", "Bai Baihe"),
    Candidate("周迅", "Zhou Xun"),
    Candidate("徐静蕾", "Xu Jinglei"),
    Candidate("章子怡", "Zhang Ziyi"),
    Candidate("周冬雨", "Zhou Dongyu"),
    Candidate("吴京", "Wu Jing"),
    Candidate("黄渤", "Huang Bo"),
    Candidate("徐峥", "Xu Zheng"),
    Candidate("葛优", "Ge You"),
    Candidate("赵本山", "Zhao Benshan"),
    Candidate("宋丹丹", "Song Dandan"),
    Candidate("郭德纲", "Guo Degang"),
    Candidate("沈腾", "Shen Teng"),
    Candidate("马丽", "Ma Li"),
    Candidate("贾玲", "Jia Ling"),
    Candidate("岳云鹏", "Yue Yunpeng"),
    Candidate("六小龄童", "Liu Xiao Ling Tong"),
    Candidate("成龙夫人", "Fania Chan"),
    # ---------- 港台 / 亚洲 ----------
    Candidate("刘亦菲", "Liu Yifei"),
    Candidate("林青霞", "Shirley Yam"),
    Candidate("王祖贤", "Joey Wong"),
    Candidate("张曼玉", "Maggie Cheung"),
    Candidate("梁朝伟", "Tony Leung Chiu-wai"),
    Candidate("吴彦祖", "Daniel Wu"),
    Candidate("彭于晏", "Eddie Peng"),
    Candidate("郭富城", "Aaron Kwok"),
    Candidate("余文乐", "Shawn Yue"),
    Candidate("陈小春", "Jordan Chan"),
    Candidate("古天乐", "Louis Koo"),
    Candidate("郑少秋", "Adam Cheng"),
    Candidate("周润发", "Chow Yun-fat"),
    Candidate("钟汉良", "Wallace Chung"),
    Candidate("霍建华", "Wallace Huo"),
    Candidate("赵雅芝", "Joyce Zhao"),
    Candidate("林心如", "Ruby Lin"),
    Candidate("陈乔恩", "Joe Chen"),
    Candidate("杨丞琳", "Rainie Yang"),
    Candidate("林志玲", "Chieko Lin"),
    Candidate("贾静雯", "Alyssa Chia"),
    Candidate("安以轩", "Ann Chia"),
    Candidate("金城武", "Takeshi Kaneshiro"),
    Candidate("梁朝伟", "Tony Leung Chiu-wai"),
    # ---------- 日韩 ----------
    Candidate("木村拓哉", "Takuya Kimura"),
    Candidate("工藤新一", "Shinichi Kudo"),
    Candidate("山口百惠", "Momoe Yamaguchi"),
    Candidate("松田圣子", "Seiko Matsuda"),
    Candidate("安室奈美惠", "Namie Amuro"),
    Candidate("滨崎步", "Ayumi Hamasaki"),
    Candidate("新垣结衣", "Yui Aragaki"),
    Candidate("石原里美", "Riho Ishihara"),
    Candidate("上白石萌音", "Mone Kamishiraishi"),
    Candidate("菅田将晖", "Masaki Suda"),
    Candidate("山崎贤人", "Kento Yamazaki"),
    Candidate("韩孝信", "Hye Jin Han"),
    Candidate("李敏镐", "Min-ho Lee"),
    Candidate("全智贤", "Jeon Ji-hyun"),
    Candidate("宋慧乔", "Song Hye-kyo"),
    Candidate("金秀贤", "Soo-hyun Kim"),
    Candidate("朴宝剑", "Bo-A Park"),
    Candidate("玄彬", "Hyun Bin"),
    Candidate("南柱赫", "Joo-hyuk Nam"),
    Candidate("裴勇俊", "Yoon Jun"),
    Candidate("BIGBANG 权志龙", "G-Dragon"),
    Candidate("朴有天", "You Tian"),
    Candidate("李敏镐", "Min-ho Lee"),
    Candidate("上户彩", "Aya Ueto"),
    Candidate("渡边谦", "Ken Watanabe"),
    Candidate("绫濑遥", "Haruka Ayase"),
    Candidate("山下智久", "Tomohisa Yamashita"),
    Candidate("福山雅治", "Masaharu Fukuyama"),
    Candidate("樱井翔", "Sho Sakurai"),
    # ---------- 好莱坞 ----------
    Candidate("汤姆·克鲁斯", "Tom Cruise", aliases=("Ethan Hunt",)),
    Candidate("汤姆·汉克斯", "Tom Hanks"),
    Candidate("莱昂纳多·迪卡普里奥", "Leonardo DiCaprio", aliases=("Jack Dawson",)),
    Candidate("小罗伯特·唐尼", "Robert Downey Jr.", aliases=("Tony Stark",)),
    Candidate("基努·里维斯", "Keanu Reeves", aliases=("Neo",)),
    Candidate("约翰尼·德普", "Johnny Depp", aliases=("Jack Sparrow",)),
    Candidate("布拉德·皮特", "Brad Pitt"),
    Candidate("乔治·克鲁尼", "George Clooney"),
    Candidate("马特·达蒙", "Matt Damon", aliases=("Jason Bourne",)),
    Candidate("本·阿弗莱克", "Ben Affleck"),
    Candidate("爱德华·诺顿", "Edward Norton"),
    Candidate("瑞恩·雷诺兹", "Ryan Reynolds"),
    Candidate("瑞安·高斯林", "Ryan Gosling"),
    Candidate("克里斯·埃文斯", "Chris Evans", aliases=("Captain America",)),
    Candidate("小罗伯特·唐尼", "Robert Downey Jr."),
    Candidate("克里斯·海默斯", "Chris Hemsworth", aliases=("Thor",)),
    Candidate("克里斯汀·斯汀顿", "Kristen Stewart"),
    Candidate("爱丽森·霍尔姆斯", "Alison Holmes"),
    Candidate("艾玛·沃特森", "Emma Watson", aliases=("Hermione Granger",)),
    Candidate("艾玛·斯通", "Emma Stone", aliases=("Gwen Stacy",)),
    Candidate("斯嘉丽·约翰逊", "Scarlett Johansson", aliases=("Black Widow",)),
    Candidate("詹妮弗·劳伦斯", "Jennifer Lawrence", aliases=("Katniss Everdeen",)),
    Candidate("安妮·海瑟薇", "Anne Hathaway", aliases=("Selina Meyer",)),
    Candidate("艾丽·范宁", "Elle Fanning"),
    Candidate("马特·达蒙", "Matt Damon"),
    Candidate("妮可·基德曼", "Nicole Kidman", aliases=("Moulin Rouge",)),
    Candidate("查理兹·塞隆", "Charlize Theron"),
    Candidate("安吉丽娜·朱莉", "Angelina Jolie", aliases=("Lara Croft",)),
    Candidate("凯特·布兰切特", "Cate Blanchett"),
    Candidate("黛安·克鲁格", "Diane Kruger"),
    Candidate("米歇尔·菲兹", "Michelle Pfeiffer"),
    Candidate("桑德拉·布洛克", "Sandra Bullock"),
    Candidate("茱莉亚·罗伯茨", "Julia Roberts", aliases=("Pretty Woman",)),
    Candidate("汤姆·克鲁斯", "Tom Cruise"),
    Candidate("杰森·斯坦森", "Jason Statham", aliases=("Transporter",)),
    Candidate("杰森·贝特曼", "Jason Bateman"),
    Candidate("本·阿弗莱克", "Ben Affleck"),
    Candidate("马特·里夫斯", "Matt Reeves"),
    Candidate("贾斯汀·汀布莱克", "Justin Timberlake", aliases=("JT",)),
    Candidate("贾斯汀·比伯", "Justin Bieber", aliases=("J Bieber",)),
    Candidate("布兰妮·斯皮尔斯", "Britney Spears"),
    Candidate("Lady Gaga", "Lady Gaga", aliases=("Stefani Germanotta",)),
    Candidate("泰勒·斯威夫特", "Taylor Swift", aliases=("Pop",)),
    Candidate("艾薇儿·拉维妮", "Avril Lavigne", aliases=("Avril Lavigne",)),
    Candidate("凯蒂·佩里", "Katy Perry", aliases=("Katherine Hudson",)),
    Candidate("碧昂丝", "Beyonce", aliases=("Beyonce Knowles",)),
    Candidate("蕾哈娜", "Rihanna", aliases=("Rihanna Fenty",)),
    Candidate("lady Gaga", "Lady Gaga"),
    Candidate("爱莉安娜·格兰德", "Ariana Grande", aliases=("Ariana",)),
    Candidate("赛琳娜·戈麦斯", "Selena Gomez", aliases=("Selena Marie Gomez",)),
    Candidate("贾斯汀·比伯", "Justin Bieber"),
    Candidate("布鲁诺·马尔斯", "Bruno Mars", aliases=("Peter Hernandez",)),
    Candidate("艾德·希兰", "Ed Sheeran", aliases=("Sunscreen",)),
    Candidate("阿黛尔", "Adele", aliases=("Adele Adkins",)),
    Candidate("碧昂丝", "Beyonce"),
    Candidate("约翰·传奇", "John Legend", aliases=("John Stephens",)),
    Candidate("玛丽亚·凯利", "Maria Carey", aliases=("Mariah Carey",)),
    Candidate("惠特尼·休斯顿", "Whitney Houston", aliases=("The Voice",)),
    Candidate("埃尔顿·约翰", "Elton John", aliases=("Rocket Man",)),
    Candidate("披头士", "The Beatles"),
    Candidate("滚石乐队", "Rolling Stones"),
    Candidate("迈克尔·杰克逊", "Michael Jackson", aliases=("King of Pop",)),
    Candidate("泰勒·斯威夫特", "Taylor Swift"),
    Candidate("贾斯汀·汀布莱克", "Justin Timberlake"),
    Candidate("克里斯·布朗", "Chris Brown", aliases=("CB",)),
    # ---------- 体育 ----------
    Candidate("梅西", "Lionel Messi", aliases=("La Pulga",)),
    Candidate("C罗", "Cristiano Ronaldo", aliases=("CR7",)),
    Candidate("内马尔", "Neymar", aliases=("Neymar Jr",)),
    Candidate("姆巴佩", "Kylian Mbappe", aliases=("Mbappe",)),
    Candidate("哈兰德", "Erling Haaland", aliases=("Haaland",)),
    Candidate("罗纳尔多", "Ronaldo Nazario"),
    Candidate("马拉多纳", "Diego Maradona"),
    Candidate("贝利", "Pelé"),
    Candidate("梅西", "Lionel Messi"),
    Candidate("科比·布莱恩特", "Kobe Bryant", aliases=("Black Mamba",)),
    Candidate("勒布朗·詹姆斯", "LeBron James", aliases=("King James",)),
    Candidate("斯蒂芬·库里", "Stephen Curry", aliases=("Chef Curry",)),
    Candidate("凯文·杜兰特", "Kevin Durant", aliases=("KD",)),
    Candidate("詹姆斯·哈登", "James Harden", aliases=("The Beard",)),
    Candidate("尼古拉·约基奇", "Nikola Jokic", aliases=("Jokic",)),
    Candidate("尤苏夫·诺尔曼", "Usain Bolt", aliases=("Lightning Bolt",)),
    Candidate("费德勒", "Roger Federer", aliases=("FedEx",)),
    Candidate("纳达尔", "Rafael Nadal", aliases=("Rafa",)),
    Candidate("德约科维奇", "Novak Djokovic", aliases=("Djokovic",)),
    Candidate("小威廉姆斯", "Serena Williams", aliases=("Queen Serena",)),
    Candidate("莎拉波娃", "Maria Sharapova"),
    Candidate("刘翔", "Liu Xiang"),
    Candidate("姚明", "Yao Ming", aliases=("Ming",)),
    Candidate("郎平", "Lang Ping", aliases=("Iron Butterfly",)),
    Candidate("谷爱凌", "Gu Ailing", aliases=("Eileen Gu",)),
    Candidate("苏炳添", "Su Bingtian", aliases=("Su",)),
    # ---------- 商业 / 科技 ----------
    Candidate("埃隆·马斯克", "Elon Musk", aliases=("Musk",)),
    Candidate("比尔·盖茨", "Bill Gates", aliases=("William Gates",)),
    Candidate("史蒂夫·乔布斯", "Steve Jobs", aliases=("Steven Jobs",)),
    Candidate("马克·扎克伯格", "Mark Zuckerberg", aliases=("Zuckerberg",)),
    Candidate("杰夫·贝佐斯", "Jeff Bezos", aliases=("Bezos",)),
    Candidate("马化腾", "Pony Ma", aliases=("Ma Huateng",)),
    Candidate("李彦宏", "Robin Li", aliases=("Li Yanhong",)),
    Candidate("马云", "Jack Ma", aliases=("Ma Yun",)),
    Candidate("雷军", "Lei Jun", aliases=("Jun Lei",)),
    Candidate("董明珠", "Dong Mingzhu", aliases=("Mingzhu",)),
    Candidate("蒂姆·库克", "Tim Cook", aliases=("Timothy Cook",)),
)


def load_candidates(
    builtin: bool = True,
    extra_path: Path | None = None,
) -> list[Candidate]:
    """加载候选表：内置 + 自定义文件。

    Args:
        builtin: 是否包含内置候选表。
        extra_path: 自定义候选文件路径，每行 ``中文名|英文名`` 或 ``英文名``。

    Returns:
        去重后的候选列表（按「英文名」去重，先到先得）。
    """
    result: list[Candidate] = []
    seen: set[str] = set()

    def _add(cand: Candidate) -> None:
        key = cand.en.strip().lower()
        if not key or key in seen:
            return
        seen.add(key)
        result.append(cand)

    if builtin:
        for c in BUILTIN_CANDIDATES:
            _add(c)

    if extra_path and extra_path.exists():
        for line in extra_path.read_text(encoding="utf-8").splitlines():
            cand = Candidate.parse(line)
            if cand is not None:
                _add(cand)

    return result
