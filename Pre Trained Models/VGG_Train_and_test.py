import torch
import torchvision.transforms as T
from torch import nn
from torch.utils.data import Dataset, DataLoader
from torchvision import datasets
import matplotlib.pyplot as plt
from torchvision.io import read_image
import torch.optim as optim
import torch.nn.functional as F
import os
import pandas as pd
import time
import copy
import shutil
from torchvision import models

torch.cuda.empty_cache()

#these hyperparameters are the ones with which we got the best result
batchSize = 8
epochs = 20
learning_rate = 1e-4
momentum = 0.9
width = 224    
height = 224   
num_classes = 8
feature_extraction = False    #if False we will do Finetuning
model_name = "vgg"
transformations = False       #if true we apply some transformations to the images
training_size = 0.8
normalization = False         #if True we apply Normalization to the images


if (feature_extraction):             
    print("We will do Feature Extraction with " + model_name)   #we start with a pretrained model and only update the final layer weights from which we derive predictions
else:   
    print("We will do Finetuning with " + model_name)     #we start with a pretrained model and update all of the model’s parameters for our new task, in essence retraining the whole model.
print("------- Define Hyper Parameters -------")
print("epochs   ->   " + str(epochs))
print("learningRate   ->   " + str(learning_rate))
print("momentum   ->   " + str(momentum))
print("transformations   ->   " + str(transformations))
print("training_size   ->   " + str(training_size))
print("normalization   ->   " + str(normalization))
print()


# define the device for the computation
device = "cuda" if torch.cuda.is_available() else "cpu"

class fishDataset(Dataset):
    def __init__(self, img_dir, labels_dir, trans=None):

        # labels stored in a csv file, each line has the form label, namefile

        self.labels = pd.read_csv(labels_dir)
        self.img_dir = img_dir
        self.transforms = trans

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):

        # getting the label
        label = self.labels.iloc[idx, 0]

        image = self.labels.iloc[idx, 1]

        # reading the image
        img_path = self.img_dir + str(label) + "/" + str(image)
        
        img = read_image(img_path)
        img = img.float() / 255
  
        # print("{}\t{}".format(img_path, img.shape), end="\n")

        if self.transforms:
            img = self.transforms(img)

        # plt.imshow(img.permute(1, 2, 0))
        # print(label)
        # plt.show()

        # return the image with the corresponding label
        if label == "ALB":
            label = 0
        elif label == "BET":
            label = 1
        elif label == "DOL":
            label = 2
        elif label == "LAG":
            label = 3
        elif label == "NoF":
            label = 4
        elif label == "OTHER":
            label = 5
        elif label == "SHARK":
            label = 6
        elif label == "YFT":
            label = 7

        return img, label

if (transformations):
  if (normalization):
    transformation = T.Compose([
        T.ToPILImage(),
        T.Resize((height, width)),
        T.RandomRotation(degrees=(0, 360)),
        T.RandomHorizontalFlip(p=0.5),
        T.RandomVerticalFlip(p=0.5),
        T.RandomAffine(degrees=0.0, translate=(0.1, 0.3)),
        T.ToTensor(),
        T.Normalize([0.4043, 0.4353, 0.3999], [0.2250, 0.2183, 0.2125]),
        ])
  else:
    transformation = T.Compose([
        T.ToPILImage(),
        T.Resize((height, width)),
        T.RandomRotation(degrees=(0, 360)),
        T.RandomHorizontalFlip(p=0.5),
        T.RandomVerticalFlip(p=0.5),
        T.RandomAffine(degrees=0.0, translate=(0.1, 0.3)),
        T.ToTensor(),
        ])
else:
  if (normalization):
    transformation = T.Compose([
      T.ToPILImage(),
      T.Resize((height, width)),
      T.ToTensor(),
      T.Normalize([0.4043, 0.4353, 0.3999], [0.2250, 0.2183, 0.2125]),
      ])
  else:
    transformation = T.Compose([
      T.ToPILImage(),
      T.Resize((height, width)),
      T.ToTensor(),
      ])


dataset = fishDataset("Image-Classification-Project/FishBoxes/Fishes/",
                      "Image-Classification-Project/FishBoxes/labels.csv", trans=transformation)

train_size = int(training_size * len(dataset))
test_size = len(dataset) - train_size
training_data, test_data = torch.utils.data.random_split(dataset, [train_size, test_size])

train_dataloader = DataLoader(training_data, batch_size=batchSize, shuffle=True)
test_dataloader = DataLoader(test_data, batch_size=batchSize, shuffle=False)

dataloaders = {'train': train_dataloader, 'val': test_dataloader}

#if we are feature extracting and only want to compute gradients for the newly initialized layer then we want all of the other parameters to not require gradients.
def set_parameter_requires_grad(model, feature_extracting):
    if feature_extracting:
        for param in model.parameters():
            param.requires_grad = False

def initialize_model(model_name, num_classes, feature_extraction, use_pretrained=True):
    model_ft = None
    input_size = 0

    if model_name == "vgg":      #VGG11_bn
        model_ft = models.vgg11_bn(pretrained=use_pretrained)
        set_parameter_requires_grad(model_ft, feature_extraction)
        num_ftrs = model_ft.classifier[6].in_features
        model_ft.classifier[6] = nn.Linear(num_ftrs,num_classes)      #redefine the last layer with the num of classes of the problem
        input_size = 224
        
    else:
        print("Invalid model name, exiting...")
        exit()

    return model_ft, input_size

# Initialize the model for this run
model_ft, input_size = initialize_model(model_name, num_classes, feature_extraction, use_pretrained=True)
model_ft = model_ft.to(device)

criterion = nn.CrossEntropyLoss()

#  Gather the parameters to be optimized/updated in this run. If we are
#  finetuning we will be updating all parameters. However, if we are
#  doing feature extract method, we will only update the parameters
#  that we have just initialized, i.e. the parameters with requires_grad is True.
params_to_update = model_ft.parameters()
print("Params to learn:")
if feature_extraction:
    params_to_update = []
    for name,param in model_ft.named_parameters():
        if param.requires_grad == True:
            params_to_update.append(param)
            print("\t",name)
else:
    for name,param in model_ft.named_parameters():
        if param.requires_grad == True:
            print("\t",name)

optimizer_ft = optim.SGD(params_to_update, learning_rate, momentum)

def train_model(model, dataloaders, criterion, optimizer, num_epochs=5):
    since = time.time()

    val_acc_history = []

    best_model_wts = copy.deepcopy(model.state_dict())
    best_acc = 0.0

    for epoch in range(num_epochs):
        print('Epoch {}/{}'.format(epoch, num_epochs - 1))
        print('-' * 10)

        # Each epoch has a training and validation phase
        for phase in ['train', 'val']:
            if phase == 'train':
                model.train()  # Set model to training mode
            else:
                model.eval()   # Set model to evaluate mode

            running_loss = 0.0
            running_corrects = 0

            # Iterate over data.
            for inputs, labels in dataloaders[phase]:
                inputs = inputs.to(device)
                labels = labels.to(device)

                # zero the parameter gradients
                optimizer.zero_grad()

                # forward
                
                with torch.set_grad_enabled(phase == 'train'):
                    # Get model outputs and calculate loss
                   
                    outputs = model(inputs)
                    loss = criterion(outputs, labels)

                    _, preds = torch.max(outputs, 1)

                    # backward + optimize only if in training phase
                    if phase == 'train':
                        loss.backward()
                        optimizer.step()

                # statistics
                running_loss += loss.item() * inputs.size(0)
                running_corrects += torch.sum(preds == labels.data)

            epoch_loss = running_loss / len(dataloaders[phase].dataset)
            epoch_acc = running_corrects.double() / len(dataloaders[phase].dataset)

            print('{} Loss: {:.4f} Acc: {:.4f}'.format(phase, epoch_loss, epoch_acc))

            # deep copy the model
            if phase == 'val' and epoch_acc > best_acc:
                best_acc = epoch_acc
                best_model_wts = copy.deepcopy(model.state_dict())
            if phase == 'val':
                val_acc_history.append(epoch_acc)

        print()

    time_elapsed = time.time() - since
    print('Training complete in {:.0f}m {:.0f}s'.format(time_elapsed // 60, time_elapsed % 60))
    print('Best val Acc: {:4f}'.format(best_acc))

    # load best model weights
    model.load_state_dict(best_model_wts)
    return model, val_acc_history


model_ft, hist = train_model(model_ft, dataloaders, criterion, optimizer_ft, num_epochs=epochs)
