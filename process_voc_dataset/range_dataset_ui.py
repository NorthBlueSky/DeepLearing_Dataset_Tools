import os
import sys
import shutil
import xml.etree.ElementTree as ET
from PyQt5.QtCore import QThread, pyqtSignal, QTime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QTextEdit,
    QFileDialog, QMessageBox
)

class FileProcessingThread(QThread):
    # 信号：当前进度/总步数、日志信息、处理完成（成功与否、提示信息）
    progressUpdated = pyqtSignal(int, int)
    logOutput = pyqtSignal(str)
    processingFinished = pyqtSignal(bool, str)

    def __init__(self, annDir, imgDir):
        super().__init__()
        self.annDir = os.path.normpath(annDir)
        self.imgDir = os.path.normpath(imgDir)
        # 默认标签文件格式：xml；图片格式支持：jpg、jpeg、png
        self.allowedImgExts = {'.jpg', '.jpeg', '.png'}

    def run(self):
        errorList = []
        try:
            # 检查文件夹是否存在
            if not os.path.isdir(self.annDir):
                raise FileNotFoundError(f"标签(Annotations)文件夹不存在：{self.annDir}")
            if not os.path.isdir(self.imgDir):
                raise FileNotFoundError(f"图片(JPEGImages)文件夹不存在：{self.imgDir}")

            # 获取标签文件列表（仅 xml 文件）并排序
            annList = sorted([f for f in os.listdir(self.annDir)
                              if f.lower().endswith('.xml')])
            # 获取图片文件列表（扩展名在 allowedImgExts 内）并排序
            imgList = sorted([f for f in os.listdir(self.imgDir)
                              if os.path.splitext(f)[1].lower() in self.allowedImgExts])
            if len(annList) != len(imgList):
                raise ValueError(f"标签文件数量({len(annList)})与图片文件数量({len(imgList)})不一致！")

            pairs = list(zip(annList, imgList))
            totalSteps = len(pairs) * 3  # 每对文件共 3 步：更新标签内容、重命名标签、重命名图片
            currentProgress = 0
            self.progressUpdated.emit(currentProgress, totalSteps)
            self.logOutput.emit(f"共找到 {len(pairs)} 对文件")

            for idx, (annFile, imgFile) in enumerate(pairs, 1):
                # 获取完整路径
                annPath = os.path.join(self.annDir, annFile)
                imgPath = os.path.join(self.imgDir, imgFile)
                # 提取图片扩展名（统一转为小写）
                img_ext = os.path.splitext(imgFile)[1].lower()

                # 【步骤 1】：更新标签 XML 文件内容（<filename> 与 <path>）
                try:
                    tree = ET.parse(annPath)
                    root = tree.getroot()
                    # 更新 <filename> 节点
                    filenameElem = root.find('filename')
                    if filenameElem is None:
                        filenameElem = ET.SubElement(root, 'filename')
                    filenameElem.text = f"{idx}{img_ext}"
                    # 更新 <path> 节点
                    pathElem = root.find('path')
                    if pathElem is None:
                        pathElem = ET.SubElement(root, 'path')
                    pathElem.text = os.path.join(self.imgDir, f"{idx}{img_ext}")
                    # 直接覆盖写入原文件
                    tree.write(annPath, encoding='utf-8', xml_declaration=True)
                    currentProgress += 1
                    self.progressUpdated.emit(currentProgress, totalSteps)
                    self.logOutput.emit(f"更新标签文件内容：{annFile}")
                except Exception as e:
                    errorList.append(f"更新标签 {annFile} 时出错：{str(e)}")
                    continue

                # 【步骤 2】：重命名标签文件为统一数字命名
                try:
                    newAnnPath = os.path.join(self.annDir, f"{idx}.xml")
                    if os.path.exists(newAnnPath):
                        os.remove(newAnnPath)
                    os.rename(annPath, newAnnPath)
                    currentProgress += 1
                    self.progressUpdated.emit(currentProgress, totalSteps)
                    self.logOutput.emit(f"重命名标签文件为：{idx}.xml")
                except Exception as e:
                    errorList.append(f"重命名标签 {annFile} 时出错：{str(e)}")

                # 【步骤 3】：重命名图片文件为统一数字命名（保留原扩展名）
                try:
                    newImgPath = os.path.join(self.imgDir, f"{idx}{img_ext}")
                    if os.path.exists(newImgPath):
                        os.remove(newImgPath)
                    os.rename(imgPath, newImgPath)
                    currentProgress += 1
                    self.progressUpdated.emit(currentProgress, totalSteps)
                    self.logOutput.emit(f"重命名图片文件为：{idx}{img_ext}")
                except Exception as e:
                    errorList.append(f"重命名图片 {imgFile} 时出错：{str(e)}")

            msg = f"文件统一转换完成，共处理 {len(pairs)} 对文件"
            if errorList:
                msg += "\n部分错误：\n" + "\n".join(errorList[:5])
                if len(errorList) > 5:
                    msg += f"\n……还有 {len(errorList)-5} 个错误"
            self.processingFinished.emit(len(errorList) == 0, msg)
        except Exception as e:
            self.processingFinished.emit(False, f"严重错误：{str(e)}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数据集统一命名工具")
        self.setMinimumSize(600, 400)
        self.initUI()

    def initUI(self):
        centralWidget = QWidget()
        self.setCentralWidget(centralWidget)
        layout = QVBoxLayout(centralWidget)

        # 文件夹选择区域
        folderWidget = QWidget()
        folderLayout = QVBoxLayout(folderWidget)
        # 标签(Annotations)文件夹选择
        self.annLineEdit = QLineEdit()
        annButton = QPushButton("选择标签(Annotations)文件夹")
        annButton.clicked.connect(lambda: self.selectFolder(self.annLineEdit))
        folderLayout.addWidget(QLabel("请输入标签(Annotations)文件夹："))
        folderLayout.addWidget(self.annLineEdit)
        folderLayout.addWidget(annButton)
        # 图片(JPEGImages)文件夹选择
        self.imgLineEdit = QLineEdit()
        imgButton = QPushButton("选择图片(JPEGImages)文件夹")
        imgButton.clicked.connect(lambda: self.selectFolder(self.imgLineEdit))
        folderLayout.addWidget(QLabel("请输入图片(JPEGImages)文件夹："))
        folderLayout.addWidget(self.imgLineEdit)
        folderLayout.addWidget(imgButton)
        layout.addWidget(folderWidget)

        # 进度条和日志显示
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setFormat("等待开始")
        layout.addWidget(self.progressBar)

        self.logTextEdit = QTextEdit()
        self.logTextEdit.setReadOnly(True)
        layout.addWidget(self.logTextEdit)

        # 开始按钮
        self.startButton = QPushButton("开始处理")
        self.startButton.clicked.connect(self.startProcessing)
        self.startButton.setFixedSize(150, 40)
        layout.addWidget(self.startButton)

    def selectFolder(self, lineEdit):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            lineEdit.setText(os.path.normpath(folder))

    def startProcessing(self):
        annDir = self.annLineEdit.text().strip()
        imgDir = self.imgLineEdit.text().strip()
        errors = []
        if not annDir:
            errors.append("请输入标签(Annotations)文件夹")
        if not imgDir:
            errors.append("请输入图片(JPEGImages)文件夹")
        if errors:
            QMessageBox.critical(self, "输入错误", "\n".join(errors))
            return

        self.startButton.setEnabled(False)
        self.logTextEdit.clear()
        self.progressBar.setFormat("处理中... %p%")

        self.worker = FileProcessingThread(annDir, imgDir)
        self.worker.progressUpdated.connect(self.updateProgress)
        self.worker.logOutput.connect(self.outputLog)
        self.worker.processingFinished.connect(self.processingFinished)
        self.worker.start()

    def updateProgress(self, current, total):
        self.progressBar.setMaximum(total)
        self.progressBar.setValue(current)

    def outputLog(self, msg):
        timeStr = QTime.currentTime().toString("hh:mm:ss")
        self.logTextEdit.append(f"[{timeStr}] {msg}")
        self.logTextEdit.ensureCursorVisible()

    def processingFinished(self, success, message):
        self.startButton.setEnabled(True)
        self.progressBar.setFormat("处理完成" if success else "处理失败")
        if success:
            QMessageBox.information(self, "处理结果", message)
        else:
            QMessageBox.critical(self, "处理结果", message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
